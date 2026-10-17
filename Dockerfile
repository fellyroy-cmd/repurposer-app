# Deploy prep only -- this image is not live anywhere yet. It exists so that
# whenever Dara creates a Render/Railway/Fly account, there's a working
# container ready to push with zero extra setup. See README "Deploying" for
# the honest status.

FROM python:3.13-slim

WORKDIR /app

# Install deps first (prod-only, no pytest/httpx) so Docker can cache this
# layer and re-installing only happens when requirements.txt actually changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

# Render/Railway/Fly all inject a $PORT env var at runtime and route traffic
# to whatever port the app actually binds -- hardcoding 8000 here would break
# on every one of those hosts. 8000 is only the local fallback.
ENV PORT=8000
EXPOSE 8000

# Never bake a real key into the image -- ANTHROPIC_API_KEY is read from the
# environment at request time (see claude_client.py) and must be set as a
# host secret on whichever platform this deploys to, never in this file or
# a committed .env.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/health', timeout=3)" || exit 1

CMD ["sh", "-c", "uvicorn repurposer.main:app --app-dir src --host 0.0.0.0 --port ${PORT}"]
