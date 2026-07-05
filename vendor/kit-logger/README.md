# kit-logger (Python)

Zero-dependency structured logger emitting one JSON object per line (timestamp,
level, component, event, plus any payload) — info/debug to stdout, warn/error to
stderr. Same event shape as `/kit/ts/logger`, so logs from TS and Python
projects can be searched the same way.

Reuse from any Python project via an editable install in `requirements.txt`:

```
-e ../../../kit/py/logger
```

Usage:

```python
from kit_logger import create_logger

log = create_logger("api.ingest")
log.info("received", filename="pricing.md", bytes=1234)
```
