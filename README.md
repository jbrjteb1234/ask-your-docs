# Ask Your Documents

**Your customers get instant answers from your own documents — with receipts.**

## The problem

Your team answers the same 20 questions every day. Customers email instead of
reading the FAQ, then wait a day for a reply — and by then they're annoyed.
Generic chatbots make things up, which is worse than no answer at all.

## What this does

A chat widget that answers strictly from *your* documents — price lists,
policies, FAQs — and shows the source for every answer. When the documents
don't cover a question it says so plainly and hands the visitor to a human,
rather than inventing something.

**Before:** repetitive questions land in your inbox; answers take hours.
**After:** visitors self-serve in seconds, on your own content, with citations —
and every question they ask is logged, so you can see exactly what your
documents are missing.

- **Grounded, not guessing** — answers come only from retrieved passages of
  your documents; every answer names its source.
- **Honest fallback** — no source, no answer: it says "I don't know" and
  offers a contact, so it never misleads a customer.
- **One-line install** — a single `<script>` tag on any page; no rebuild.
- **A content roadmap** — the admin view logs unanswered questions, which is
  the exact list of gaps worth filling.

Running cost is roughly a penny per answered question (see [Costs](#costs)).

## Packages (fixed price)

- **Starter — £600:** up to ~25 documents, branded widget, citations, human
  fallback. One week.
- **Standard — £1,200:** + site scrape, admin view, unanswered-questions
  report, one refresh cycle.
- **Retainer — £150–£400/mo:** monthly re-ingest, content updates from the
  unanswered list, tuning.

## Embed the widget

One tag, anywhere before `</body>`:

```html
<script src="https://your-app.up.railway.app/widget.js"
        data-name="Your Business Name"
        data-colour="#0f766e"></script>
```

(Swap the host for your deployed URL — the widget derives its API base from
its own script `src`, so nothing else to configure.)

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
