# Node.js TokenGraph example

This project is analyzed statically; TokenOptiPy never executes it.

```console
tokenoptipy build examples/nodejs-token-graph --output node-example-out --language auto
tokenoptipy hotspots --graph node-example-out/graph.json
tokenoptipy explain SYSTEM_PROMPT --graph node-example-out/graph.json
tokenoptipy path SYSTEM_PROMPT conversationHistory --graph node-example-out/graph.json
```
