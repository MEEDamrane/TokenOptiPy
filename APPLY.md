# Apply the TokenOptiPy MCP + traceability patch

Copy this overlay into the root of the TokenOptiPy repository, replacing files with the same path.

```bash
cp -R TokenOptiPy_MCP_Traceability/. /path/to/TokenOptiPy/
cd /path/to/TokenOptiPy
python -m pip install -e ".[dev]"
pytest -q
ruff check .
mypy src
python -m build
cd vscode-extension
npm run check
npx @vscode/vsce package
```

The overlay also includes the previously prepared QA fixes for modern secret redaction, structure-sensitive prompt validation, semantic polarity checks, and graph edge performance.

## Expected VS Code result

Only one TokenOptiPy UI element is displayed: the status-bar traceability item.

## Important

The GitHub integration available during preparation was read-only and returned HTTP 403 for repository writes. The files therefore need to be applied locally and pushed using your own Git credentials.
