# TokenGraph JSON schema overview

The public artifact is `tokenoptipy-out/graph.json`.

## String classification (graph 0.6)

Prompt-compatible nodes retain `type: "prompt"` so existing readers keep working. Their
`attributes` now include `classification`, `confidence`, `reason`, and `evidence`.
Classifications are `llm_prompt`, `candidate_prompt`, `developer_message`,
`error_message`, `log_message`, `ui_text`, `config_text`, `documentation`, and
`unknown_string`. Only a string with a statically established path to a verified model
call is promoted to `llm_prompt`. Ordinary classified strings may use `type: "string"`.

Graph 0.6 adds `PROMPT_TO_MODEL_CALL`, `CONTEXT_TO_PROMPT`,
`MODEL_CALL_TO_RESPONSE`, `PROMPT_BUILT_FROM`, `SYSTEM_MESSAGE_OF`, and
`USER_MESSAGE_OF`. Legacy edges such as `FLOWS_TO`, `INCLUDES`, and `USES_VARIABLE`
remain serialized during the migration. The reader accepts graphs without the new
attributes and continues to default missing versions to 0.5.

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
