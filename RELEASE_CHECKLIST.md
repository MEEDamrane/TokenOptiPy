# Release checklist

- [ ] `pytest -q` passes.
- [ ] `ruff check .` passes.
- [ ] CLI smoke test builds the example project.
- [ ] `graph.html`, `graph.json` and `TOKEN_REPORT.md` open correctly.
- [ ] README and changelog describe the release.
- [ ] Version matches in `pyproject.toml`, `__init__.py` and `CITATION.cff`.
- [ ] Source archive contains no generated secrets or private prompts.
- [ ] Tag `v0.2.0` is signed or annotated.
- [ ] GitHub release includes checksums.
