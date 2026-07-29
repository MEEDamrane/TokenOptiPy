# TokenGraph JSON schema overview

The public artifact is `tokenoptipy-out/graph.json`.

## Node

```json
{
  "id": "prompt:0123456789ab",
  "type": "prompt",
  "label": "CLASSIFY_PROMPT",
  "path": "services/llm_service.py",
  "line": 12,
  "end_line": 20,
  "static_tokens": 184,
  "attributes": {
    "source_kind": "python_assignment",
    "preview": "You are a support assistant…",
    "content_hash": "sha256…",
    "placeholders": ["customer_message"]
  }
}
```

## Edge

```json
{
  "source": "prompt:0123456789ab",
  "target": "model_call:abcdef012345",
  "type": "FLOWS_TO",
  "attributes": {"role": "prompt"}
}
```

## Finding

```json
{
  "code": "TG005",
  "severity": "warning",
  "node_id": "context:abcdef012345",
  "message": "Potentially unbounded conversation input…",
  "suggestion": "Apply a message window…",
  "estimated_saving_tokens": 0,
  "confidence": 0.72
}
```
