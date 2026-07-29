# Quickstart

```bash
git clone https://github.com/MEEDamrane/TokenOptiPy.git
cd TokenOptiPy
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Build a graph:

```bash
tokenoptipy build path/to/your/project
```

Inspect results:

```bash
tokenoptipy stats
tokenoptipy hotspots
tokenoptipy query "history"
```

Open `tokenoptipy-out/graph.html` locally.
