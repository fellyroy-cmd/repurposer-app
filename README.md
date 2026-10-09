# Repurposer App

Paste a YouTube script, get it rewritten for another platform — in Dara Obafemi's brand voice, via the Claude API. This is the backend for turning a one-person Claude Desktop workflow (`/repurpose`) into something any creator can use on the web.

**Status: Week 2 of 4 — complete.** All five platforms work end-to-end: X (Twitter) threads, LinkedIn posts, Instagram carousels, TikTok scripts, and newsletter sections. A `/repurpose-all` endpoint fans out to every platform in one call. There is no UI yet (Week 3) and nothing is deployed yet (Week 4).

## What it does right now

- `GET /health` — confirms the service is up.
- `POST /repurpose` — takes `{"script": "...", "platform": "..."}` and calls the Claude API with brand-voice rules baked into a platform-specific system prompt.
  - `platform: "x"`, `"linkedin"`, `"tiktok"`, or `"newsletter"` → returns `{"platform": "...", "content": "...", "carousel": null}` — plain text, ready to copy-paste (TikTok is a spoken script with a few bracketed on-screen-text notes; newsletter is one section of the weekly digest).
  - `platform: "instagram"` → returns `{"platform": "instagram", "content": null, "carousel": {"caption": "...", "slides": ["...", "..."]}}` — a **typed object**, not a wall of text. Claude is instructed to respond with only JSON; the app parses and validates that JSON into a fixed shape (`caption` + a list of `slides`) before it ever reaches the response. If Claude's output doesn't match that shape, the endpoint returns a clear `502` instead of guessing or dropping slides silently.
- `POST /repurpose-all` — takes `{"script": "..."}` (no `platform` needed — it runs all five) and returns `{"results": [...]}`, one entry per platform, each entry shaped exactly like a single `/repurpose` response. Reuses the same parse-and-validate path, so Instagram still comes back as a typed carousel inside the fan-out, not a wall of text. Same fail-loud rule applies: if the API key is missing, this returns a `503` immediately instead of quietly returning a partial list.

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

curl -X POST http://127.0.0.1:8000/repurpose \
  -H "Content-Type: application/json" \
  -d '{"script": "Paste your YouTube script here.", "platform": "tiktok"}'

curl -X POST http://127.0.0.1:8000/repurpose \
  -H "Content-Type: application/json" \
  -d '{"script": "Paste your YouTube script here.", "platform": "newsletter"}'

curl -X POST http://127.0.0.1:8000/repurpose-all \
  -H "Content-Type: application/json" \
  -d '{"script": "Paste your YouTube script here."}'
```

If `ANTHROPIC_API_KEY` is missing, `/repurpose` and `/repurpose-all` both return a clear `503` error explaining exactly what's wrong — neither fakes a response or runs a silent "demo mode".

## Cost, honestly

Every `/repurpose` call makes one real request to the Claude API (model set via `MODEL` in `.env`, default `claude-sonnet-5`). You're billed per token by Anthropic for both the system prompt + your script (input) and the generated post (output). A typical YouTube script (a few hundred words) plus a short response costs a small fraction of a cent to a few cents per call, depending on script length and platform — the Instagram prompt asks for 5-8 slides plus a caption, so it runs a bit more output tokens than X or LinkedIn. **`/repurpose-all` makes five separate Claude requests — one per platform — so it costs roughly 5x a single `/repurpose` call, not one combined call.** Check Anthropic's current per-model pricing before running this against a lot of scripts. There is no caching or batching yet, so every call is a fresh charge.

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
    main.py              # FastAPI app — /health, /repurpose, /repurpose-all
tests/                  # pytest suite, all mocked
```

## Roadmap

- **Week 1 (done):** scaffold, `/health`, `/repurpose` for X only, mocked tests.
- **Week 2 (done):** all five platforms wired up (X, LinkedIn, Instagram carousel, TikTok, newsletter) plus `/repurpose-all` to fan out to every platform in one call.
- **Week 3:** minimal web UI — paste box, platform toggles, copyable result cards.
- **Week 4:** deploy to a live URL, lock the API key as a host secret, basic rate limiting.

Part of [Project Alpha](https://github.com/fellyroy-cmd) — Dara Obafemi's 9-month build-in-public AI career project.
