# Repurposer App

Paste a YouTube script, get it rewritten for another platform — in Dara Obafemi's brand voice, via the Claude API. This is the backend for turning a one-person Claude Desktop workflow (`/repurpose`) into something any creator can use on the web.

**Status: Week 2 of 4 (all platforms, in progress).** Three platforms work end-to-end: X (Twitter) threads, LinkedIn posts, and Instagram carousels. TikTok and newsletter are next, then a `/repurpose-all` endpoint that fans out to every platform in one call. There is no UI yet (Week 3) and nothing is deployed yet (Week 4).

## What it does right now

- `GET /health` — confirms the service is up.
- `POST /repurpose` — takes `{"script": "...", "platform": "..."}` and calls the Claude API with brand-voice rules baked into a platform-specific system prompt.
  - `platform: "x"` or `"linkedin"` → returns `{"platform": "...", "content": "...", "carousel": null}` — plain text, ready to copy-paste.
  - `platform: "instagram"` → returns `{"platform": "instagram", "content": null, "carousel": {"caption": "...", "slides": ["...", "..."]}}` — a **typed object**, not a wall of text. Claude is instructed to respond with only JSON; the app parses and validates that JSON into a fixed shape (`caption` + a list of `slides`) before it ever reaches the response. If Claude's output doesn't match that shape, the endpoint returns a clear `502` instead of guessing or dropping slides silently.

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

curl -X POST http://127.0.0.1:8000/repurpose \
  -H "Content-Type: application/json" \
  -d '{"script": "Paste your YouTube script here.", "platform": "linkedin"}'

curl -X POST http://127.0.0.1:8000/repurpose \
  -H "Content-Type: application/json" \
  -d '{"script": "Paste your YouTube script here.", "platform": "instagram"}'
```

If `ANTHROPIC_API_KEY` is missing, `/repurpose` returns a clear `503` error explaining exactly what's wrong — it never fakes a response or runs a silent "demo mode".

## Cost, honestly

Every `/repurpose` call makes one real request to the Claude API (model set via `MODEL` in `.env`, default `claude-sonnet-5`). You're billed per token by Anthropic for both the system prompt + your script (input) and the generated post (output). A typical YouTube script (a few hundred words) plus a short response costs a small fraction of a cent to a few cents per call, depending on script length and platform — the Instagram prompt asks for 5-8 slides plus a caption, so it runs a bit more output tokens than X or LinkedIn. Check Anthropic's current per-model pricing before running this against a lot of scripts. There is no caching or batching yet, so every call is a fresh charge.

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
    models.py           # Pydantic request/response shapes (incl. InstagramCarousel)
    main.py              # FastAPI app — /health, /repurpose
tests/                  # pytest suite, all mocked
```

## Roadmap

- **Week 1 (done):** scaffold, `/health`, `/repurpose` for X only, mocked tests.
- **Week 2 (in progress):** LinkedIn and Instagram carousel added — done. TikTok and newsletter prompts, then `/repurpose-all` to fan out to all five platforms in one call — next.
- **Week 3:** minimal web UI — paste box, platform toggles, copyable result cards.
- **Week 4:** deploy to a live URL, lock the API key as a host secret, basic rate limiting.

Part of [Project Alpha](https://github.com/fellyroy-cmd) — Dara Obafemi's 9-month build-in-public AI career project.
