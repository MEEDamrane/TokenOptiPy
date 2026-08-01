'use strict';

const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const childProcess = require('child_process');
const util = require('util');
const execFile = util.promisify(childProcess.execFile);

const PROVIDER_ID = 'tokenoptipy.mcp';
const MANAGED_BEGIN = '# BEGIN TOKENOPTIPY MCP (managed by TokenOptiPy VS Code)';
const MANAGED_END = '# END TOKENOPTIPY MCP';

/** @type {vscode.StatusBarItem | undefined} */
let statusBar;
/** @type {vscode.FileSystemWatcher[]} */
let watchers = [];
/** @type {vscode.EventEmitter<void> | undefined} */
let definitionsChanged;
let lastAutoBuildTrace = '';

function configuration() {
  return vscode.workspace.getConfiguration('tokenoptipy');
}

function pythonPath() {
  return String(configuration().get('pythonPath', 'python')).trim() || 'python';
}

function tracePath(folder) {
  return path.join(folder.uri.fsPath, '.tokenoptipy', 'trace.jsonl');
}

function tomlString(value) {
  return JSON.stringify(String(value));
}

function managedCodexBlock(folder) {
  const root = folder.uri.fsPath;
  const trace = tracePath(folder);
  return [
    MANAGED_BEGIN,
    '[mcp_servers.tokenoptipy]',
    `command = ${tomlString(pythonPath())}`,
    'args = ["-m", "tokenoptipy.mcp_server"]',
    'startup_timeout_sec = 20',
    'tool_timeout_sec = 120',
    `env = { TOKENOPTIPY_WORKSPACE_ROOT = ${tomlString(root)}, TOKENOPTIPY_TRACE_FILE = ${tomlString(trace)}, PYTHONUTF8 = "1", PYTHONUNBUFFERED = "1" }`,
    MANAGED_END
  ].join('\n');
}

async function configureCodex(folder) {
  if (!vscode.workspace.isTrusted || !configuration().get('configureCodex', true)) {
    return;
  }
  const directory = path.join(folder.uri.fsPath, '.codex');
  const configPath = path.join(directory, 'config.toml');
  await fs.promises.mkdir(directory, { recursive: true });
  let content = '';
  try {
    content = await fs.promises.readFile(configPath, 'utf8');
  } catch (error) {
    if (error.code !== 'ENOENT') {
      throw error;
    }
  }
  const block = managedCodexBlock(folder);
  const start = content.indexOf(MANAGED_BEGIN);
  const end = content.indexOf(MANAGED_END);
  let updated;
  if (start >= 0 && end >= start) {
    updated = content.slice(0, start) + block + content.slice(end + MANAGED_END.length);
  } else {
    updated = content.trimEnd();
    updated += `${updated ? '\n\n' : ''}${block}\n`;
  }
  if (updated !== content) {
    await fs.promises.writeFile(configPath, updated, 'utf8');
  }
}

function serverDefinitions() {
  if (!vscode.workspace.isTrusted) {
    return [];
  }
  return (vscode.workspace.workspaceFolders || []).map((folder) => new vscode.McpStdioServerDefinition({
    label: `TokenOptiPy — ${folder.name}`,
    command: pythonPath(),
    args: ['-m', 'tokenoptipy.mcp_server'],
    cwd: folder.uri,
    env: {
      PYTHONUTF8: '1',
      PYTHONUNBUFFERED: '1',
      TOKENOPTIPY_WORKSPACE_ROOT: folder.uri.fsPath,
      TOKENOPTIPY_TRACE_FILE: tracePath(folder)
    },
    version: '0.3.0'
  }));
}

async function readRecentEvents(filePath, limit) {
  try {
    const raw = await fs.promises.readFile(filePath, 'utf8');
    const lines = raw.split(/\r?\n/).filter(Boolean).slice(-limit);
    return lines.flatMap((line) => {
      try {
        const value = JSON.parse(line);
        return value && typeof value === 'object' ? [value] : [];
      } catch {
        return [];
      }
    });
  } catch (error) {
    if (error.code === 'ENOENT') {
      return [];
    }
    throw error;
  }
}

function formatTimestamp(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value || '') : date.toLocaleTimeString();
}

async function refreshStatusBar() {
  if (!statusBar) {
    return;
  }
  const limit = Number(configuration().get('traceLimit', 20));
  const collected = [];
  for (const folder of vscode.workspace.workspaceFolders || []) {
    const events = await readRecentEvents(tracePath(folder), Math.max(1, Math.min(limit, 100)));
    for (const event of events) {
      collected.push({ ...event, folder: folder.name, filePath: tracePath(folder) });
    }
  }
  collected.sort((left, right) => String(left.timestamp).localeCompare(String(right.timestamp)));
  const latest = collected[collected.length - 1];
  if (!latest) {
    statusBar.text = '$(tools) TokenOptiPy MCP · ready';
    statusBar.tooltip = new vscode.MarkdownString(
      '**TokenOptiPy MCP**\n\nNo tool call has been traced yet. Prompt text and tool arguments are never stored.'
    );
    statusBar.command = undefined;
    return;
  }

  const tool = String(latest.tool || 'unknown');
  const status = String(latest.status || 'unknown');
  const duration = latest.duration_ms == null ? '' : ` · ${latest.duration_ms}ms`;
  if (status === 'started') {
    statusBar.text = `$(sync~spin) TokenOptiPy · ${tool}`;
  } else if (status === 'error') {
    statusBar.text = `$(error) TokenOptiPy · ${tool}`;
  } else {
    statusBar.text = `$(check) TokenOptiPy · ${tool}${duration}`;
  }

  const recent = collected.slice(-Math.max(1, Math.min(limit, 100))).reverse();
  const tooltip = new vscode.MarkdownString('', true);
  tooltip.appendMarkdown('**TokenOptiPy MCP traceability**\n\n');
  tooltip.appendMarkdown(`Latest: \`${tool}\` — **${status}**${duration}  \n`);
  tooltip.appendMarkdown(`Trace: \`${String(latest.trace_id || '')}\`  \n`);
  tooltip.appendMarkdown(`Workspace: \`${String(latest.folder || '')}\`  \n`);
  tooltip.appendMarkdown(`Time: ${formatTimestamp(latest.timestamp)}  \n`);
  if (latest.summary) {
    tooltip.appendMarkdown(`Summary: ${String(latest.summary).replace(/[<>]/g, '')}\n\n`);
  }
  tooltip.appendMarkdown(`Recent events: **${recent.length}**  \n`);
  tooltip.appendMarkdown('_The trace excludes prompts, secrets, and tool arguments._');
  statusBar.tooltip = tooltip;
  statusBar.command = 'tokenoptipy.openTrace';
  if (latest.tool === 'inspect_workspace' && latest.status === 'completed' && latest.trace_id !== lastAutoBuildTrace && configuration().get('buildGraphAfterInspect', false)) {
    lastAutoBuildTrace = latest.trace_id;
    const folder = (vscode.workspace.workspaceFolders || []).find((item) => item.name === latest.folder);
    if (folder) await buildGraph(folder, false);
  }
}

function activeFolder() {
  const folders = vscode.workspace.workspaceFolders || [];
  if (!folders.length) throw new Error('Open a workspace folder first.');
  return folders[0];
}

async function runTokenOptiPy(folder, args) {
  const env = { ...process.env, TOKENOPTIPY_WORKSPACE_ROOT: folder.uri.fsPath, PYTHONUTF8: '1' };
  return execFile(pythonPath(), ['-m', 'tokenoptipy', ...args], { cwd: folder.uri.fsPath, env, windowsHide: true });
}

async function configureMcpClients() {
  const folder = activeFolder();
  await runTokenOptiPy(folder, ['mcp-config', '.', '--client', 'all']);
  await runTokenOptiPy(folder, ['agent-init', '.', '--client', 'all']);
  vscode.window.showInformationMessage('TokenOptiPy MCP clients and agent instructions configured.');
}

async function buildGraph(folder = activeFolder(), notify = true) {
  await runTokenOptiPy(folder, ['build', '.', '--output', 'tokenoptipy-out']);
  if (notify) vscode.window.showInformationMessage('TokenGraph built successfully.');
}

async function openGraph(folder = activeFolder()) {
  const uri = vscode.Uri.file(path.join(folder.uri.fsPath, 'tokenoptipy-out', 'graph.html'));
  try { await vscode.workspace.fs.stat(uri); } catch { throw new Error('Build the TokenGraph first.'); }
  await vscode.env.openExternal(uri);
}

async function buildAndOpenGraph() {
  const folder = activeFolder(); await buildGraph(folder, false); await openGraph(folder);
}

async function showPromptFlow() {
  const folder = activeFolder();
  const graphPath = path.join(folder.uri.fsPath, 'tokenoptipy-out', 'graph.json');
  const graph = JSON.parse(await fs.promises.readFile(graphPath, 'utf8'));
  const prompts = graph.nodes.filter((node) => node.type === 'prompt');
  const picked = await vscode.window.showQuickPick(prompts.map((node) => ({ label: node.label, description: `${node.static_tokens || 0} tokens`, node })));
  if (!picked) return;
  const { stdout } = await runTokenOptiPy(folder, ['prompt-flow', picked.node.id, '--graph', 'tokenoptipy-out/graph.json']);
  const document = await vscode.workspace.openTextDocument({ language: 'json', content: stdout });
  await vscode.window.showTextDocument(document, { preview: true });
}

async function openLatestTrace() {
  const folders = vscode.workspace.workspaceFolders || [];
  const candidates = [];
  for (const folder of folders) {
    const filePath = tracePath(folder);
    try {
      const stat = await fs.promises.stat(filePath);
      candidates.push({ filePath, modified: stat.mtimeMs });
    } catch (error) {
      if (error.code !== 'ENOENT') {
        throw error;
      }
    }
  }
  candidates.sort((left, right) => right.modified - left.modified);
  if (!candidates.length) {
    return;
  }
  const document = await vscode.workspace.openTextDocument(candidates[0].filePath);
  await vscode.window.showTextDocument(document, { preview: true });
}

function disposeWatchers() {
  for (const watcher of watchers) {
    watcher.dispose();
  }
  watchers = [];
}

function installWatchers(context) {
  disposeWatchers();
  for (const folder of vscode.workspace.workspaceFolders || []) {
    const pattern = new vscode.RelativePattern(folder, '.tokenoptipy/trace.jsonl');
    const watcher = vscode.workspace.createFileSystemWatcher(pattern);
    watcher.onDidCreate(refreshStatusBar, undefined, context.subscriptions);
    watcher.onDidChange(refreshStatusBar, undefined, context.subscriptions);
    watcher.onDidDelete(refreshStatusBar, undefined, context.subscriptions);
    watchers.push(watcher);
    context.subscriptions.push(watcher);
  }
}

async function configureWorkspaces() {
  for (const folder of vscode.workspace.workspaceFolders || []) {
    await configureCodex(folder);
  }
}

/** @param {vscode.ExtensionContext} context */
async function activate(context) {
  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 90);
  statusBar.name = 'TokenOptiPy MCP traceability';
  statusBar.text = '$(tools) TokenOptiPy MCP · ready';
  statusBar.show();

  definitionsChanged = new vscode.EventEmitter();
  context.subscriptions.push(
    statusBar,
    definitionsChanged,
    vscode.commands.registerCommand('tokenoptipy.openTrace', openLatestTrace),
    vscode.commands.registerCommand('tokenoptipy.configureMcpClients', () => configureMcpClients().catch(showError)),
    vscode.commands.registerCommand('tokenoptipy.buildGraph', () => buildGraph().catch(showError)),
    vscode.commands.registerCommand('tokenoptipy.buildAndOpenGraph', () => buildAndOpenGraph().catch(showError)),
    vscode.commands.registerCommand('tokenoptipy.openGraph', () => openGraph().catch(showError)),
    vscode.commands.registerCommand('tokenoptipy.showPromptFlow', () => showPromptFlow().catch(showError)),
    vscode.lm.registerMcpServerDefinitionProvider(PROVIDER_ID, {
      onDidChangeMcpServerDefinitions: definitionsChanged.event,
      provideMcpServerDefinitions: async () => serverDefinitions(),
      resolveMcpServerDefinition: async (server) => vscode.workspace.isTrusted ? server : undefined
    }),
    vscode.workspace.onDidChangeWorkspaceFolders(async () => {
      installWatchers(context);
      await configureWorkspaces();
      definitionsChanged.fire();
      await refreshStatusBar();
    }),
    vscode.workspace.onDidGrantWorkspaceTrust(async () => {
      await configureWorkspaces();
      definitionsChanged.fire();
      await refreshStatusBar();
    }),
    vscode.workspace.onDidChangeConfiguration(async (event) => {
      if (!event.affectsConfiguration('tokenoptipy')) {
        return;
      }
      await configureWorkspaces();
      definitionsChanged.fire();
      await refreshStatusBar();
    })
  );

  installWatchers(context);
  await configureWorkspaces();
  await refreshStatusBar();
}

function showError(error) { vscode.window.showErrorMessage(`TokenOptiPy: ${error.message || error}`); }

function deactivate() {
  disposeWatchers();
}

module.exports = { activate, deactivate };
