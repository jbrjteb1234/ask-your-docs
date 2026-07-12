# Ask Your Documents

**Your customers get instant answers from your own documents — with receipts.**

**Watch it work (3 minutes):** [Loom demo](https://www.loom.com/share/aae3b8fce505454182f2319cc2bee1f9)

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
- **Honest fallback** — no source, no answer: it says "I don't know" and offers
  a contact, so it never misleads a customer.
- **One-line install** — a single `<script>` tag on any page; no rebuild.
- **A content roadmap** — the admin view logs unanswered questions, which is
  the exact list of gaps worth filling.

Live demo: https://independent-strength-production-070f.up.railway.app/demo

## Fixed prices

- **Starter — £600:** up to ~25 documents, branded widget, citations, human
  fallback, delivered in a week.
- **Standard — £1,200:** + ingest of your existing site pages, the admin
  view, an unanswered-questions report, one content refresh cycle.
- **Retainer — £150–£400/mo:** monthly re-ingest, content updates driven by
  the unanswered-questions log, tuning.

## Tech stack

| Layer | Choice | Version |
|-------|--------|---------|
| Language / runtime | Python | 3.12 (Docker `python:3.12-slim`) |
| Web framework | FastAPI | 0.139 |
| ASGI server | Uvicorn | 0.50 |
| Validation | Pydantic | 2.13 |
| Answering LLM | Anthropic Claude (`claude-sonnet-5` default, via `ANTHROPIC_MODEL`) | SDK 0.116 |
| Embeddings | Voyage AI `voyage-3.5-lite` (1024-dim), REST via httpx | — |
| Database | Supabase (hosted PostgreSQL) + `pgvector` (HNSW, cosine) | supabase-py 2.31 |
| PDF extraction | pypdf | 6.14 |
| HTTP client | httpx | 0.28 |
| Config / uploads | python-dotenv 1.2, python-multipart 0.0.32 | — |
| Frontend | Vanilla JS widget (Shadow DOM) + HTML/CSS admin — no framework | — |
| Shared kit | `kit-logger`, `kit-claude` (vendored under `vendor/`) | — |
| Deploy | Docker → Railway (push-to-`main` auto-deploy) | — |

Deliberately boring: no vector-DB service (retrieval is one Postgres
function), no LangChain, no ORM, no frontend framework. Keeps running cost near
zero and the whole thing debuggable.

## Architecture

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

Code layout (`src/`):

| Module | Responsibility |
|--------|----------------|
| `main.py` | FastAPI app: routes, CORS, admin auth, rate limit |
| `config.py` | Env-backed config + honest missing-config reporting |
| `extract.py` | PDF (per page) and text/markdown → text units |
| `chunker.py` | Fixed-size + overlap chunking |
| `embeddings.py` | Voyage embedder behind a swappable `Embedder` interface |
| `db.py` | Supabase access: store, per-file replace/delete, vector retrieval |
| `rag.py` | Ask pipeline: retrieve → grounded Claude answer → citations |

`vendor/` holds a **copy** of the shared kit (`/kit/py` in the private
monorepo) so the app deploys standalone — never edit `vendor/` directly; edit
the canonical kit and re-sync (see [DEPLOY.md](DEPLOY.md)).

## Prerequisites

- Python 3.12+
- Free accounts on **Supabase**, **Anthropic** (billing enabled — no free
  tier), and **Voyage AI** (200M free embedding tokens)

## Local setup

1. Create a venv and install (the shared kit is already vendored into
   `vendor/` and installed via `requirements.txt` — nothing extra to do):

   ```
   cd projects/p2-docs-assistant/app
   python -m venv .venv
   .venv\Scripts\activate        # Windows (source .venv/bin/activate elsewhere)
   pip install -r requirements.txt
   ```

2. Create a [Supabase](https://supabase.com) project and run
   `supabase/schema.sql` in the SQL editor (enables pgvector, creates the
   `chunks` + `questions` tables and the `match_chunks` function). The schema
   defines the embedding size as `vector(1024)`; if you change
   `EMBEDDINGS_MODEL` to one with a different dimension, set `EMBEDDINGS_DIM`
   to match **and** update `vector(N)` in `schema.sql` to the same number.

3. Copy `.env.example` to `.env` and fill it in (see Configuration below).

4. Run the API:

   ```
   uvicorn src.main:app --reload
   ```

   It serves on **http://127.0.0.1:8000** — open `/demo` for the widget,
   `/admin` for the dashboard, `/health` to check config.

5. Smoke test (ingests `samples/`, asks one answerable, one nuanced and one
   unanswerable question):

   ```
   python scripts/demo.py
   ```

   Voyage's free tier allows 3 requests/min, so the first run may pace slowly
   (the client retries automatically) — that's expected, not an error.

## Configuration (environment variables)

`.env` locally; set the same values in Railway's Variables for deployment.

| Variable | Required | Purpose |
|----------|----------|---------|
| `SUPABASE_URL` | yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | Supabase secret key (server-side; bypasses RLS) |
| `ANTHROPIC_API_KEY` | yes (ask) | Anthropic API key |
| `VOYAGE_API_KEY` | yes | Voyage AI embeddings key |
| `ADMIN_KEY` | yes (admin) | Shared key for `/admin`, `/ingest`, `/documents` |
| `CONTACT_EMAIL` | recommended | Shown as the human handoff on fallbacks |
| `ANTHROPIC_MODEL` | no | Answering model (default `claude-sonnet-5`; `claude-opus-4-8` for max quality, `claude-haiku-4-5` for min cost) |
| `EMBEDDINGS_PROVIDER` | no | Only `voyage` implemented today (see note) |
| `EMBEDDINGS_MODEL` | no | Default `voyage-3.5-lite` |
| `EMBEDDINGS_DIM` | no | Default `1024` — must match `vector(N)` in the schema |
| `TOP_K` | no | Chunks retrieved per question (default 5) |
| `MIN_SIMILARITY` | no | Below this best-match score → honest fallback (default 0.30) |
| `RATE_LIMIT_PER_MIN` | no | Public `/ask` requests per IP per minute (default 10) |
| `TRUST_PROXY` | prod | Set `true` **only** behind a proxy you control (e.g. Railway/nginx) so the rate limiter reads the real client IP; leaving it off on a direct-exposed host is safer, but on Railway you want it `true` |
| `PORT` | no | Injected by the platform (Railway); defaults to 8000 locally |

`EMBEDDINGS_PROVIDER` note: the code is *designed* to be provider-swappable
(thin `Embedder` interface), but only Voyage is implemented — switching
providers requires adding a branch in `get_embedder()`, not just changing the
env var.

## Ingesting documents

There is **no upload button** in the admin UI — ingest is API-only, admin-key
protected, and accepts `.pdf`, `.txt`, `.md` (no site scraping / DOCX yet):

```
curl -H "X-Admin-Key: $ADMIN_KEY" \
     -F files=@pricing.md -F files=@policies.pdf \
     https://<your-host>/ingest
```

Re-uploading a filename **replaces** that file's chunks (the refresh path).
To load a website, save the pages to PDF/text first. Delete a file's chunks
with `DELETE /documents/{filename}` (admin key).

## Using the admin view

Open `/admin`, paste your `ADMIN_KEY` into the key field (it's kept in the
browser and sent as the `X-Admin-Key` header on subsequent requests). You get
the unanswered-questions log (your content roadmap), recent questions with the
sources used per answer, and the document list.

## Embed the widget

One tag, anywhere before `</body>`:

```html
<script src="https://independent-strength-production-070f.up.railway.app/widget.js"
        data-name="Your Business Name"
        data-colour="#0f766e"></script>
```

The widget derives its API base from its own script `src`, so the host above
is the only thing to change per deployment. It renders in a Shadow DOM
(isolated from host-page CSS) and inserts all answer text via `textContent`
(so a document can't inject markup into the customer's page).

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

Every ingest, embedding, retrieval and Claude call emits a structured JSON log
line with timings, token counts and estimated cost.

## Costs

Well under a penny per answered question, almost entirely the Claude call. The
default `claude-sonnet-5` ($3/$15 per Mtok) runs roughly **$0.008/question**;
`claude-opus-4-8` ($5/$25) is ~$0.013 for higher quality, `claude-haiku-4-5`
($1/$5) is cheaper still — switch via `ANTHROPIC_MODEL`. Embeddings are
~$0.0000003/question on Voyage `voyage-3.5-lite` ($0.02/1M tokens, first 200M
free). Supabase's free tier covers the demo comfortably. **Anthropic is the one
component with no free tier — a funded account is required from the first
question.**

## Security posture

- **CORS is open** (`*`) so the widget can POST from any customer site, but
  only `Content-Type` is allowed through — the admin endpoints can't be called
  cross-origin.
- **Admin auth is a single shared key** (`ADMIN_KEY`), constant-time compared.
  Anyone with it can read all logged customer questions; rotate by changing
  the env var and redeploying.
- **The rate limit is in-memory per process** — it resets on redeploy and is
  not shared across replicas, so keep the service at a single instance.

## Deployment

Deploys as a Docker container on Railway with p