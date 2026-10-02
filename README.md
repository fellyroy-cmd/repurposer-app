# Repurposer App

Paste a YouTube script, get it rewritten for another platform — in Dara Obafemi's brand voice, via the Claude API. This is the backend for turning a one-person Claude Desktop workflow (`/repurpose`) into something any creator can use on the web.

**Status: Week 1 of 4 (scaffold).** One endpoint works end-to-end: `POST /repurpose` for X (Twitter) threads. LinkedIn, Instagram, TikTok, and newsletter are coming in Week 2. There is no UI yet (Week 3) and nothing is deployed yet (Week 4).

## What it does right now

- `GET /health` — confirms the service is up.
- `POST /repurpose` — takes `{"script": "...", "platform": "x"}`, calls the Claude API with brand-voice rules baked into the system prompt, and returns `{"platform": "x", "content": "..."}` (an X thread).

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env   # then paste your real ANTHROPIC_API_KEY into .env
uvicorn repurposer.main:app --reload --app-dir src
```

Then:

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/repurpose \
  -H "Content-Type: application/json" \
  -d '{"script": "Paste your YouTube script here.", "platform": "x"}'
```

If `ANTHROPIC_API_KEY` is missing, `/repurpose` returns a clear `503` error explaining exactly what's wrong — it never fakes a response or runs a silent "demo mode".

## Cost, honestly

Every `/repurpose` call makes one real request to the Claude API (model set via `MODEL` in `.env`, default `claude-sonnet-5`). You're billed per token by Anthropic for both the system prompt + your script (input) and the generated post (output). A typical YouTube script (a few hundred words) plus a short X thread response costs a small fraction of a cent to a few cents per call, depending on script length — check Anthropic's current per-model pricing before running this against a lot of scripts. There is no caching or batching yet, so every call is a fresh charge.

## Tests

```bash
pytest
```

Tests mock the Claude API client entirely — no API key or network call needed to run the suite. That's intentional: CI (and anyone cloning this repo) can verify the wiring is correct without spending a cent.

## Project layout

```
src/repurposer/
    config.py          # model id + brand-voice system prompts, all in one place
    claude_client.py    # thin wrapper around the Anthropic SDK (mockable)
    models.py           # Pydantic request/response shapes
    main.py              # FastAPI app — /health, /repurpose
tests/                  # pytest suite, all mocked
```

## Roadmap

- **Week 1 (done):** scaffold, `/health`, `/repurpose` for X only, mocked tests.
- **Week 2:** all five platforms (X, LinkedIn, Instagram carousel, TikTok, newsletter) via `/repurpose-all`.
- **Week 3:** minimal web UI — paste box, platform toggles, copyable result cards.
- **Week 4:** deploy to a live URL, lock the API key as a host secret, basic rate limiting.

Part of [Project Alpha](https://github.com/fellyroy-cmd) — Dara Obafemi's 9-month build-in-public AI career project.
