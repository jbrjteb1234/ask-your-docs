# Ask Your Documents — support assistant (M1)

Answers questions strictly from YOUR business documents, with citations —
or an honest "I don't know" instead of a made-up answer. M1 is the bare API
proving the spine: ingest → retrieve → cited answer. (Widget, admin view and
the full sales-page README arrive in M2/M3.)

## How it works

```
upload PDF / text / markdown
        │
        ▼
extract → chunk (fixed size + overlap) → embed (Voyage) → Supabase pgvector
                                                              │
POST /ask {question} → embed question → top-k chunks ─────────┘
        │
        ▼
Claude answers ONLY from those chunks → {answer, citations, confident}
   weak retrieval or not in the docs → {fallback message, confident: false}
```

## Local setup

1. Python 3.11+. Create a venv and install:

   ```
   cd projects/p2-docs-assistant/app
   python -m venv .venv
   .venv\Scripts\activate        # Windows (source .venv/bin/activate elsewhere)
   pip install -r requirements.txt
   ```

2. Create a [Supabase](https://supabase.com) project and run
   `supabase/schema.sql` in the SQL editor (enables pgvector, creates the
   `chunks` table + `match_chunks` function).

3. Copy `.env.example` to `.env` and fill in the keys (Supabase, Anthropic,
   [Voyage AI](https://dash.voyageai.com) — 200M free embedding tokens).

4. Run the API:

   ```
   uvicorn src.main:app --reload
   ```

5. Smoke test (ingests `samples/`, asks three questions — one answerable,
   one nuanced, one unanswerable):

   ```
   python scripts/demo.py
   ```

## Endpoints

| Method | Path | What it does |
|--------|------|--------------|
| GET | `/health` | Status + any missing env config |
| POST | `/ingest` | Multipart upload of `.pdf` / `.txt` / `.md`; re-uploading a filename replaces its chunks |
| POST | `/ask` | `{"question": "..."}` → `{answer, citations, confident}` |
| GET | `/documents` | Ingested files with chunk counts |
| DELETE | `/documents/{filename}` | Remove a file's chunks |

Every ingest, embedding, retrieval and Claude call emits a structured JSON
log line with timings, token counts and estimated cost.

## Costs

Embeddings: Voyage `voyage-3.5-lite` at $0.02 per million tokens (first 200M
free) — swappable via `EMBEDDINGS_PROVIDER`/`EMBEDDINGS_MODEL`. Answering:
Claude (model from `ANTHROPIC_MODEL`), token counts and USD cost logged per
call. Supabase free tier covers the demo comfortably.
