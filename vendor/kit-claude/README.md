# kit-claude (Python)

Claude API wrapper mirroring `/kit/ts/claude`: official `anthropic` SDK with
retries + backoff and a 60s timeout, model from `ANTHROPIC_MODEL` env (default
`claude-opus-4-8`), per-call token counts + estimated USD cost logged as a
`claude_call` JSON line through kit-logger, optional JSON-schema structured
output, and `build_request_params()` for dry-run previews that cannot drift
from the real request.

kit-logger is a /kit sibling (not on PyPI) so it is NOT declared as a pip
dependency — install both together via editable installs in `requirements.txt`:

```
-e ../../../kit/py/logger
-e ../../../kit/py/claude
```

Usage:

```python
from kit_claude import call_claude

result = call_claude(
    prompt="...",
    system="...",
    json_schema={"type": "object", "properties": {...}},  # optional
)
print(result.text, result.cost_usd)
```
