# Repurposer App

Paste a YouTube script, get it rewritten for another platform — in Dara Obafemi's brand voice, via the Claude API. This is the backend for turning a one-person Claude Desktop workflow (`/repurpose`) into something any creator can use on the web.

**Status: Week 4 of 4 — in progress.** All five platforms work end-to-end: X (Twitter) threads, LinkedIn posts, Instagram carousels, TikTok scripts, and newsletter sections. A `/repurpose-all` endpoint fans out to every platform (or just the ones you pick) **concurrently** — all five run at once instead of one after another, so a full fan-out takes roughly as long as the single slowest platform call (~13s) instead of the sum of all five (~60s). The web UI is a full brand redesign (obsidian + hot pink, matching Dara's design system) with per-platform icons, a live word/character counter on the paste box, skeleton loading states while Claude is working, Instagram slides rendered as individual tiles, a "Copy all" button alongside each platform's own Copy button, and Ctrl+Enter as a keyboard shortcut to submit. An optional `ACCESS_CODE` locks the token-spending endpoints behind a shared password (the UI shows a code field only when one is required) — so a public deploy can't be used by a stranger to spend Dara's Anthropic credit. The token-spending endpoints are also rate-limited (default: 10 requests per 60 seconds per client). Errors from Claude's API itself (bad key, Anthropic-side rate limit, network failure, their outage) are caught and turned into clear messages, never a raw crash. A `Dockerfile` plus a `render.yaml` blueprint are in the repo so it's deploy-ready in one click once there's an account — **but there is still no live URL.** That needs a real Render/Railway/Fly account and host secrets that only Dara can create.

## What it does right now

- `GET /` — serves a one-page UI: paste box + a checkbox per platform (all on by default) + "Repurpose" button that calls `/repurpose-all` with only the checked platforms and renders each result as a readable card (Instagram's slides render as a numbered list, everything else as plain copyable text). Each card has a "Copy" button that puts that platform's content straight on the clipboard — for Instagram, it flattens the caption + numbered slides into one block of text so there's something sensible to paste.
- `GET /health` — confirms the service is up.
- `POST /repurpose` — takes `{"script": "...", "platform": "..."}` and calls the Claude API with brand-voice rules baked into a platform-specific system prompt.
  - `platform: "x"`, `"linkedin"`, `"tiktok"`, or `"newsletter"` → returns `{"platform": "...", "content": "...", "carousel": null}` — plain text, ready to copy-paste (TikTok is a spoken script with a few bracketed on-screen-text notes; newsletter is one section of the weekly digest).
  - `platform: "instagram"` → returns `{"platform": "instagram", "content": null, "carousel": {"caption": "...", "slides": ["...", "..."]}}` — a **typed object**, not a wall of text. Claude is instructed to respond with only JSON; the app parses and validates that JSON into a fixed shape (`caption` + a list of `slides`) before it ever reaches the response. If Claude's output doesn't match that shape, the endpoint returns a clear `502` instead of guessing or dropping slides silently.
- `POST /repurpose-all` — takes `{"script": "...", "platforms": [...]}` and returns `{"results": [...]}`, one entry per requested platform, each entry shaped exactly like a single `/repurpose` response. `platforms` is optional — omit it (or send an empty list) and it runs all five, same as before. Pass a subset (e.g. `["x", "linkedin"]`) to only spend tokens on the platforms you actually want; an unknown platform name in the list returns a `400`, same rule as `/repurpose`. Every requested platform's Claude call runs **in parallel** (a thread pool, one worker per platform) instead of one after another, so the wait is the slowest single call, not the sum of all of them. Reuses the same parse-and-validate path, so Instagram still comes back as a typed carousel inside the fan-out, not a wall of text. Same fail-loud rule applies: if the API key is missing, this returns a `503` immediately instead of quietly returning a partial list.
- `GET /config` — tells the UI whether an access code is required (`access_code_required: true/false`) and which platforms are supported, so the frontend can show or hide the access-code field without hardcoding anything. Never returns the code itself.

**Rate limiting:** `/repurpose` and `/repurpose-all` share one request budget per client IP — **10 requests per 60-second window by default** (both configurable via `RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` in `.env`). Go over the limit and you get a clear `429` explaining exactly what happened, not a silent drop or a queued request. `GET /health` is never rate-limited — a monitoring check should always get through. This is a simple in-memory counter (no new dependency), which is fine for this project's single-process deploy target but means the budget resets if the process restarts and isn't shared across multiple server instances.

**Input validation:** `script` must be at least 1 character and no more than **50,000 characters** (`config.MAX_SCRIPT_LENGTH`) on both `/repurpose` and `/repurpose-all`. Both limits are enforced by Pydantic before the request handler runs at all — an empty or oversized paste gets a `422` with zero Claude API calls made and zero hits against the rate limit above, so a bad paste never costs a cent or eats into your request budget. 50,000 characters is roughly a 2-hour spoken transcript — well past what any of the five platform prompts are designed to compress into one post, and on `/repurpose-all` an oversized script would otherwise multiply that wasted cost by all five platforms in a single request.

The same rule applies to platform names: `platform` on `/repurpose` and every entry inside the `platforms` list on `/repurpose-all` must be a non-empty string. An empty string ("") is still technically a valid `str`, so without this it would have slipped past Pydantic and only been caught deep inside the endpoint's "unsupported platform" check — a confusing `400` ("Unsupported platform ''") that reads like a typo got misreported rather than an empty field. Now it gets the same clear `422` as an empty script, at the same validation layer, before `call_claude` ever runs.

`/repurpose-all`'s `platforms` list also can't contain the same platform twice (e.g. `["x", "x"]` from a buggy frontend or a double-clicked checkbox) — that would otherwise fan out to one real Claude call per duplicate, charging twice for an identical result. A repeat returns a `400` naming the duplicate before any call is made, for free.

**Access code (optional, for public deploys):** set `ACCESS_CODE` in `.env` and `/repurpose` and `/repurpose-all` both require a matching `X-Access-Code` header on every request — a wrong or missing code returns `401` before the rate limit is even checked and before any Claude call happens. Leave `ACCESS_CODE` blank (the default) and both endpoints work with no header at all, which is what you want running the app on your own machine. `GET /config` tells the UI whether a code is currently required, so the code field only shows up on deploys that actually need it.

## Running it

```bash
pip install -r requirements-dev.txt   # prod deps + pytest/httpx for testing
cp .env.example .env   # then paste your real ANTHROPIC_API_KEY into .env
uvicorn repurposer.main:app --reload --app-dir src
```

(Just running the app with no plan to test it? `pip install -r requirements.txt` alone is enough — it skips pytest/httpx, which are dev-only.)

Open `http://127.0.0.1:8000/` in a browser for the UI, or hit the API directly:

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

curl -X POST http://127.0.0.1:8000/repurpose-all \
  -H "Content-Type: application/json" \
  -d '{"script": "Paste your YouTube script here.", "platforms": ["x", "linkedin"]}'
```

If `ANTHROPIC_API_KEY` is missing, `/repurpose` and `/repurpose-all` both return a clear `503` error explaining exactly what's wrong — neither fakes a response or runs a silent "demo mode".

**Beyond a missing key:** if the key is set but wrong, if Anthropic's own API is rate-limiting your account, or if their API is down/unreachable, both endpoints still fail loudly with a specific, readable error instead of an unhandled `500` and a raw stack trace:

| What happened | Status | Example message |
|---|---|---|
| `ANTHROPIC_API_KEY` not set at all | `503` | "ANTHROPIC_API_KEY is not set..." |
| Key is set but Claude rejects it as invalid | `502` | "Claude rejected the API key as invalid..." |
| Anthropic's own rate limit on your account | `502` | "Claude's API rate limit was hit..." |
| Network/timeout reaching Anthropic | `503` | "Couldn't reach the Claude API..." |
| Anthropic-side server error (their outage) | `502` | "Claude's API returned an error (status 500)..." |

None of these messages ever include the API key itself — only Anthropic's own (key-free) error text, re-wrapped into a clearer sentence.

## Cost, honestly

Every `/repurpose` call makes one real request to the Claude API (model set via `MODEL` in `.env`, default `claude-sonnet-5-5`). You're billed per token by Anthropic for both the system prompt + your script (input) and the generated post (output). A typical YouTube script (a few hundred words) plus a short response costs a small fraction of a cent to a few cents per call, depending on script length and platform — the Instagram prompt asks for 5-8 slides plus a caption, so it runs a bit more output tokens than X or LinkedIn. **`/repurpose-all` makes one Claude request per platform you select** — all five by default, or fewer if you uncheck some in the UI (or pass a shorter `platforms` list directly) — so unchecking three platforms cuts the cost of that call roughly in half, not just the response size. Check Anthropic's current per-model pricing before running this against a lot of scripts. There is no caching or batching yet, so every call is a fresh charge.

## Tests

```bash
pytest
```

Tests mock the Claude API client entirely — no API key or network call needed to run the suite. That's intentional: CI (and anyone cloning this repo) can verify the wiring is correct without spending a cent.

## Deploying (prep done, not live yet)

A `Dockerfile` + `.dockerignore` **and** a `render.yaml` blueprint are in the repo so the app is ready to deploy the moment there's a Render/Railway/Fly account to deploy it to — this is **prep, not a live deploy**. There is no public URL yet.

What's already handled in the image:
- Only `requirements.txt` (prod deps) gets installed — pytest and httpx stay out of the deployed image, they're dev-only (`requirements-dev.txt`).
- The app binds to whatever `$PORT` the host injects at runtime, not a hardcoded port — Render, Railway, and Fly all route traffic this way, and a hardcoded port would silently break on all three.
- A `HEALTHCHECK` hits `/health` every 30s so the host knows if the container is actually alive.
- `ANTHROPIC_API_KEY` is never baked into the image or copied in from `.env` (`.dockerignore` excludes it) — it has to be set as a host secret on whichever platform this lands on, read fresh from the environment the same way it already is locally.

`render.yaml` is a **Render Blueprint** — on Render, "New > Blueprint" picks this repo up automatically, builds the `Dockerfile`, wires the health check to `/health`, and prompts for the two secrets (`ANTHROPIC_API_KEY`, `ACCESS_CODE`) on first deploy without ever storing them in the file (`sync: false`). This removes the manual "create a web service, point it at the Dockerfile, set env vars by hand" steps — but someone still has to own the Render account and click deploy. That's the one remaining blocker.

To try it locally once Docker Desktop is installed:

```bash
docker build -t repurposer-app .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=your-real-key repurposer-app
```

Still to come before this is actually "shipped": create the Render (or Railway/Fly) account, deploy the blueprint, set `ANTHROPIC_API_KEY` and `ACCESS_CODE` as that host's secrets, and push.

## Project layout

```
src/repurposer/
    config.py          # model id + brand-voice system prompts, all in one place
    claude_client.py    # thin wrapper around the Anthropic SDK (mockable), wraps SDK errors into clear, safe messages
    rate_limit.py        # in-memory per-client rate limiter for the token-spending endpoints
    models.py           # Pydantic request/response shapes (incl. InstagramCarousel)
    main.py              # FastAPI app — /, /health, /repurpose, /repurpose-all
    static/index.html    # the one-page UI (plain HTML + vanilla JS, no build step)
tests/                  # pytest suite, all mocked
Dockerfile              # deploy prep — builds a container, not yet pushed anywhere live
render.yaml             # Render Blueprint — one-click deploy once there's an account
.dockerignore           # keeps .env, tests/, and dev-only files out of the image
requirements.txt        # prod deps only (what the Docker image installs)
requirements-dev.txt     # prod deps + pytest/httpx (what you need to run the test suite)
```

## Roadmap

- **Week 1 (done):** scaffold, `/health`, `/repurpose` for X only, mocked tests.
- **Week 2 (done):** all five platforms wired up (X, LinkedIn, Instagram carousel, TikTok, newsletter) plus `/repurpose-all` to fan out to every platform in one call.
- **Week 3 (done):** minimal web UI — paste box + a checkbox toggle per platform (pick a subset instead of always all five) + Repurpose button wired to `/repurpose-all`, results render as cards, each card has a one-click Copy button.
- **Week 4 (in progress):** basic rate limiting on the token-spending endpoints (done — 10 req/60s per client by default) · `Dockerfile` + `render.yaml` deploy prep (done — see "Deploying" above) · hardened error handling for Claude API failures beyond a missing key (done — see "Cost, honestly" above) · input validation on script length and on empty/duplicate platform names so a bad request gets a free `422`/`400` instead of a spent (or doubled) API call (done — see "Input validation" above) · optional `ACCESS_CODE` so a public deploy can't be used by a stranger (done — see "Input validation" above) · brand UI redesign + parallel fan-out on `/repurpose-all` (done, Oct 21) · actually deploying to a live URL + locking the API key as a host secret, still to come.

Part of [Project Alpha](https://github.com/fellyroy-cmd) — Dara Obafemi's 9-month build-in-public AI career project.
