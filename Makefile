.PHONY: test lint build demo clean

test:
	PYTHONPATH=src pytest -q

lint:
	ruff check .

build:
	python -m build

demo:
	PYTHONPATH=src python -m tokenoptipy build examples/token_graph_project --output example-out

clean:
	rm -rf build dist .pytest_cache .ruff_cache example-out tokenoptipy-out
