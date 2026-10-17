"""
Static checks on the Dockerfile and .dockerignore -- no Docker daemon
required, so this runs in plain CI same as everything else.

These don't prove the image builds (that needs `docker build`, which isn't
available in every environment this runs in), but they catch the mistakes
that matter most for a deploy-prep file: a baked-in secret, or a hardcoded
port that would silently break on Render/Railway/Fly.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DOCKERFILE = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
DOCKERIGNORE = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")


def test_dockerfile_exists_and_is_not_empty():
    assert DOCKERFILE.strip()


def test_dockerfile_never_hardcodes_an_api_key():
    # The only mention of the key should be the comment explaining it's
    # read from the environment -- never a literal ANTHROPIC_API_KEY=<value>.
    assert "ANTHROPIC_API_KEY=" not in DOCKERFILE
    assert "ENV ANTHROPIC_API_KEY" not in DOCKERFILE


def test_dockerfile_does_not_copy_the_env_file():
    # .env must never end up inside the image -- it should only be excluded
    # via .dockerignore, not copied and then deleted.
    assert "COPY .env" not in DOCKERFILE


def test_dockerfile_binds_to_the_platform_port_not_a_hardcoded_one():
    # Render/Railway/Fly inject $PORT at runtime and route to it. A
    # hardcoded "--port 8000" in CMD would break on all three hosts.
    assert "${PORT}" in DOCKERFILE
    assert "--port 8000" not in DOCKERFILE


def test_dockerfile_declares_a_healthcheck_against_the_health_endpoint():
    assert "HEALTHCHECK" in DOCKERFILE
    assert "/health" in DOCKERFILE


def test_dockerfile_installs_prod_requirements_only():
    # requirements.txt (prod) should be installed; requirements-dev.txt
    # (pytest, httpx) should never be referenced -- no reason to ship test
    # tooling inside a deployed image.
    assert "requirements.txt" in DOCKERFILE
    assert "requirements-dev.txt" not in DOCKERFILE


def test_dockerignore_excludes_env_and_git_and_tests():
    for entry in (".env", ".git/", "tests/", "__pycache__/"):
        assert entry in DOCKERIGNORE, f"expected {entry!r} in .dockerignore"


def test_requirements_files_stay_split_prod_vs_dev():
    prod = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    dev = (REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")

    # pytest/httpx are test-only -- if they ever leak into the prod file,
    # the Docker image would silently start shipping test tooling again.
    assert "pytest" not in prod
    assert "httpx" not in prod

    # requirements-dev.txt must still pull in everything prod needs too,
    # via the -r include, so `pip install -r requirements-dev.txt` alone
    # is enough to run the app locally for development.
    assert "-r requirements.txt" in dev
    assert "pytest" in dev
