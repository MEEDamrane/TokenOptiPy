# Architecture

TokenOptiPy 0.2 contains two related engines.

## TokenGraph Engine

```text
Project scanner
  -> file parsers
  -> graph builder
  -> graph analysis rules
  -> JSON / Markdown / HTML reports
```

### Scanner

`scanner.py` discovers supported files, ignores common generated directories, enforces a maximum file size and computes SHA-256 fingerprints.

### Extractors

`python_extractor.py` uses Python's AST. It extracts functions, prompt-like assignments, f-string variables and common model calls without executing the analyzed project.

Text and template files are treated as prompt resources. JSON strings are extracted when their path looks prompt-related or their content is long enough to represent context.

### Graph

`graph_models.py` defines typed nodes, edges and findings. The serialized graph intentionally avoids full prompt bodies. It stores redacted previews, hashes and numeric similarity signatures.

### Analysis

`graph_engine.py` computes hotspots, flow paths, duplicate relationships and rule-based findings. Querying is local keyword search, not an LLM call.

### Reporting

`graph_reporting.py` produces:

- `graph.json`
- `TOKEN_REPORT.md`
- `graph.html`

The HTML viewer is self-contained and uses an SVG graph with local JavaScript.

## Standalone Prompt Optimizer

The v0.1 modules remain available for deterministic transformations of a single prompt. Candidates are accepted only after constraint checks and token comparison.
