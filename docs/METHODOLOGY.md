# Methodology

## Objective

TokenOptiPy maps the token-bearing components of an LLM application before proposing optimization work.

A model call can be described as:

```text
static instructions
+ prompt templates
+ examples
+ conversation history
+ retrieved documents
+ user input
+ output budget
```

Static analysis can measure the first components and identify dynamic flows. Exact runtime values require instrumentation.

## Analysis stages

1. Discover supported project files.
2. Parse source without executing it.
3. Extract prompts, variables, functions and model calls.
4. Create typed graph relations.
5. Estimate static tokens locally.
6. detect large prompts, overlap and unbounded contexts.
7. rank prompts and model calls by estimated token size.
8. produce inspectable artifacts.

## Similarity

Prompt bodies are not stored in the graph. Similarity uses:

- SHA-256 for exact equality;
- MinHash-style numeric signatures for approximate Jaccard similarity;
- hashed-term containment to detect one prompt embedded in another.

These methods are approximate and can produce false positives or false negatives.

## Safety

TokenOptiPy does not automatically remove dynamic context from a project. Findings are recommendations with confidence levels. Developers should run task-quality evaluations before changing production prompts.
