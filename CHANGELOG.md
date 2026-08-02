# Changelog

## 0.5.0 — 2026-08-02

- Add an extensible `LanguageAdapter` registry and project detection for PHP, Java, C, C++, C#/.NET, Go, and Rust.
- Add conservative multilingual prompt, import, function, resource, flow, and model-call extraction.
- Add repeatable CLI language selection, `tokenoptipy languages`, MCP `get_language_support`, and VS Code language support configuration.
- Expand security exclusions, parser diagnostics, graph metadata, configuration validation, and local-only documentation.

## 0.4.0 — 2026-08-01

- Add fully static JavaScript, JSX, ESM, CommonJS, TypeScript, and TSX analysis using bundled Tree-sitter grammar wheels.
- Add automatic Python/Node.js project detection, language selection, safe exclusions, and validated `tokenoptipy.config.json` configuration.
- Extend TokenGraph, MCP tools, reports, examples, tests, and the VS Code command center for hybrid projects.

## 0.3.0 — 2026-08-01

- Added universal MCP and agent configuration generators.
- Added prompt-flow and graph-report MCP tools.
- Rebuilt the self-contained TokenGraph UI and expanded the VS Code commands.

## Unreleased

### Fixed

- Redact possible credentials from Python assignment and inline-call previews.
- Prevent project content from terminating the inline script in HTML reports.
- Avoid treating ordinary JSON schema values, Markdown files, and YAML settings as prompts.
- Recognize chat-message content and prompt-keyed YAML resources.

### Changed

- CI now runs strict type checking and verifies that distribution packages build.
- Reports describe heuristic savings as potential rather than guaranteed.

## 0.2.0 — 2026-07-29

### Added

- TokenGraph project scanner.
- Python AST extraction for prompts, variables, functions and model calls.
- Text, JSON, YAML-like and Jinja prompt resources.
- Typed graph nodes and edges.
- `build`, `stats`, `hotspots`, `explain`, `path` and `query` commands.
- Local HTML, Markdown and JSON graph reports.
- overlap, large-prompt, dynamic-context and possible-secret findings.
- project fingerprint check through `build --update`.
- four graph-focused automated tests.

### Changed

- Default graph token counting uses the local dependency-free counter.
- Project positioning expanded from a single-prompt optimizer to a project-level token-flow analyzer.

## 0.1.0 — 2026-07-29

- Initial offline prompt analyzer, optimizer, evaluator and CLI.
