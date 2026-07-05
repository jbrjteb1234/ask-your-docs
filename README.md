# Ask Your Documents — support assistant (M2)

Answers questions strictly from YOUR business documents, with citations —
or an honest "I don't know" plus a route to a human instead of a made-up
answer. Ships as a chat widget any website can embed with one script tag,
backed by an admin view that turns unanswered questions into a content
roadmap. (Demo polish and the full sales-page README arrive in M3.)

## Embed the widget

One tag, anywhere before `</body>`:

```html
<script src="https://YOUR-HOST/widget.js"
        data-name="Your Business Name"
        data-colour="#0f766e"></script>
```

`/demo` serves a plain host page with the widget already embedded. Answers
show their sources; when the documents don't cover a question the visitor
gets an honest fallback plus a `CONTACT_EMAIL` handoff link.

## Admin view

`/admin` (shared key — `ADMIN_KEY` in `.env`, sent as `X-Admin-Key`):
unanswered-questions log (the content roadmap), recent questions with the
sources used per answer, and the ingested document list. `/ingest` and
`/documents` require the same key — only `/ask`, `/widget.js`, `/demo` and
`/health` are public. Public `/ask` is rate-limited per IP
(`RATE_LIMIT_PER_MIN`, default 10).

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

| Method | Path | Auth | What it does |
|--------|------|------|--------------|
| GET | `/health` | public | Status + any missing env config |
| POST | `/ask` | public, rate-limited | `{"question": "..."}` → `{answer, citations, confident}` (+ `contact` on fallbacks) |
| GET | `/widget.js` | public | The embeddable widget |
| GET | `/demo` | public | Plain host page with the widget embedded |
| GET | `/admin` | key via page | Admin view |
| GET | `/admin/questions` | X-Admin-Key | Question log; `?unanswered=true` for the roadmap list |
| POST | `/ingest` | X-Admin-Key | Multipart upload of `.pdf` / `.txt` / `.md`; re-uploading a filename replaces its chunks |
| GET | `/documents` | X-Admin-Key | Ingested files with chunk counts |
| DELETE | `/documents/{filename}` | X-Admin-Key | Remove a file's chunks |

Every ingest, embedding, retrieval and Claude call emits a structured JSON
log line with timings, token counts and estimated cost.

## Costs

Embeddings: Voyage `voyage-3.5-lite` at $0.02 per million tokens (first 200M
free) — swappable via `EMBEDDINGS_PROVIDER`/`EMBEDDINGS_MODEL`. Answering:
Claude (model from `ANTHROPIC_MODEL`), token counts and USD cost logged per
call. Supabase free tier covers the demo comfortably.
