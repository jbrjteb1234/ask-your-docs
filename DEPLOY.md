# DEPLOY.md — Railway deployment & update runbook

The app deploys as a Docker container on Railway, from the public repo
**github.com/jbrjteb1234/ask-your-docs**. Supabase, Anthropic and Voyage are
external services reached over their APIs — nothing else to host.

## One-time: connect Railway to the repo

1. **Railway → your service → Settings → Source** → connect the GitHub repo
   `jbrjteb1234/ask-your-docs`, branch `main`. (Or delete the empty service
   and use **New → Deploy from GitHub repo**.) Railway detects the
   `Dockerfile` and builds it.
2. **Variables** tab → Raw Editor → paste (fill the three secrets from your
   local `app/.env`; do not commit them):
   ```
   SUPABASE_URL=https://<your-project>.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=<your Supabase secret key>
   ANTHROPIC_API_KEY=<your Anthropic key>
   VOYAGE_API_KEY=<your Voyage key>
   ADMIN_KEY=<a long random string>
   CONTACT_EMAIL=<your support email>
   TRUST_PROXY=true
   ```
   `TRUST_PROXY=true` matters on Railway — the app sits behind Railway's proxy,
   so this makes the per-IP rate limiter read the real client IP.
3. **Networking → Generate Domain** → note the `https://…up.railway.app` URL.
4. In Supabase, confirm `supabase/schema.sql` has been run (chunks + questions
   tables).
5. Ingest content (admin-only): from a machine with the keys,
   `API_BASE=https://…up.railway.app python scripts/demo.py` seeds the sample
   business, or POST your own files to `/ingest` with the `X-Admin-Key` header.
6. Update the widget embed snippet (README + any customer page) to the real
   host, and smoke-test `/demo` and `/admin`.

## Auto-deploy

Once connected, every push to `main` on `ask-your-docs` triggers a rebuild and
redeploy automatically. Secrets live only in Railway's Variables, never in the
repo. Roll back from Railway's deployment history if a push breaks something.

## Updating the app (monorepo → public repo)

The canonical source is the private monorepo at
`projects/p2-docs-assistant/app`. The shared kit is vendored into `./vendor`
so the app deploys standalone; the canonical kit is `/kit/py`. After changing
either, re-sync and publish:

```
# from the monorepo root, after committing your changes
git subtree split --prefix=projects/p2-docs-assistant/app -b p2-deploy
git push deploy p2-deploy:main        # 'deploy' = the ask-your-docs remote
git branch -D p2-deploy               # tidy the temp split branch
```

If the kit changed, first re-copy it into `./vendor` (see the vendor note in
`requirements.txt`) and commit, then run the sync above.

## Notes / known limitations (from the M2 review)
- Re-ingest (`replace_chunks`) is delete-then-insert without a transaction; a
  failure mid-operation could drop a document's chunks — re-ingest recovers.
- `/documents` inherits PostgREST's 1000-row cap (irrelevant at demo scale).
- Multi-file `/ingest` partial failure keeps already-stored files but the
  error response doesn't enumerate them (each is logged).
