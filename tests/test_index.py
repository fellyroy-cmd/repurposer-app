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
