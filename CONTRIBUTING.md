# Contributing

Thank you for helping improve TokenOptiPy.

## Development setup

```bash
git clone https://github.com/MEEDamrane/TokenOptiPy.git
cd TokenOptiPy
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,tiktoken]'
pytest
ruff check .
mypy src
```

## Pull requests

- Keep changes focused.
- Add tests for new behavior.
- Document new transformations and their safety assumptions.
- Do not introduce an implicit external API call.
- Explain how semantic or task quality is validated.

## Adding a transformation

Each transformation should include:

1. a precise pattern;
2. safety assumptions;
3. a confidence level;
4. tests for preserved placeholders, numbers, and negations;
5. a benchmark or token-count example;
6. documentation of known failure modes.
