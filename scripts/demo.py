"""Three-question smoke test — the M1 verification artefact.

Ingests the sample docs, then asks one answerable, one nuanced and one
unanswerable question, printing the three JSON responses.

Usage: start the API (uvicorn src.main:app), then: python scripts/demo.py
Optional: API_BASE env var (default http://127.0.0.1:8000).
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")
SAMPLES = Path(__file__).resolve().parents[1] / "samples"
# /ingest and /documents are admin-protected from M2 on.
ADMIN_HEADERS = {"X-Admin-Key": os.environ.get("ADMIN_KEY", "")}

QUESTIONS = [
    ("answerable", "How much does it cost to hire an e-mountain bike for a full day?"),
    ("nuanced", "I need to cancel my booking two days before pick-up - do I get my money back?"),
    ("unanswerable", "Do you sell gift vouchers?"),
]


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=120)

    health = client.get("/health").json()
    if health.get("missing_config"):
        print("NOT CONFIGURED - set these in app/.env and retry:")
        for name in health["missing_config"]:
            print(f"  - {name}")
        return 1

    files = sorted(p for p in SAMPLES.iterdir() if p.suffix in (".pdf", ".txt", ".md"))
    if not files:
        print(f"no sample files found in {SAMPLES}")
        return 1

    print(f"Ingesting {len(files)} sample file(s): {', '.join(p.name for p in files)}")
    response = client.post(
        "/ingest",
        files=[("files", (p.name, p.read_bytes())) for p in files],
        headers=ADMIN_HEADERS,
    )
    if response.status_code != 200:
        print(f"INGEST FAILED ({response.status_code}): {response.text}")
        return 1
    print(json.dumps(response.json(), indent=2))

    print("\nStored documents:")
    print(json.dumps(client.get("/documents", headers=ADMIN_HEADERS).json(), indent=2))

    failures = 0
    for label, question in QUESTIONS:
        print(f"\n--- {label}: {question}")
        response = client.post("/ask", json={"question": question})
        if response.status_code != 200:
            print(f"ASK FAILED ({response.status_code}): {response.text}")
            failures += 1
            continue
        body = response.json()
        print(json.dumps(body, indent=2))
        expect_confident = label != "unanswerable"
        if body["confident"] != expect_confident:
            print(f"UNEXPECTED: confident={body['confident']}, expected {expect_confident}")
            failures += 1
        if expect_confident and not body["citations"]:
            print("UNEXPECTED: confident answer without citations")
            failures += 1

    print(f"\n{'SMOKE TEST PASSED' if failures == 0 else f'SMOKE TEST FAILED ({failures} problem(s))'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
