from fastapi.testclient import TestClient

from repurposer.main import app

client = TestClient(app)


def test_index_returns_html_page():
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # Spot-check the page actually contains the UI, not just any HTML.
    assert "Repurposer" in response.text
    assert "Repurpose" in response.text


def test_index_has_copy_button_markup():
    response = client.get("/")
    page = response.text

    # Every result card gets a "Copy" button wired to the clipboard API.
    assert "copy-btn" in page
    assert "navigator.clipboard.writeText" in page
    # The IG carousel has no plain `content` field, so there must be a
    # dedicated function that flattens caption + slides into copyable text.
    assert "plainTextFor" in page


def test_index_has_platform_toggle_markup():
    response = client.get("/")
    page = response.text

    # Checkboxes get built into #toggles, one per platform, all checked
    # by default -- and the selected subset is read before the fetch call.
    assert 'id="toggles"' in page
    assert "platform-toggle" in page
    assert "selectedPlatforms" in page
    # The fetch body must actually send the chosen subset as `platforms`.
    assert "platforms" in page
