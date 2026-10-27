"""Web UI is served by the same FastAPI process as the API."""


def _client():
    from fastapi.testclient import TestClient
    from omni_one.api.fastapi_app import create_omni_one_app

    return TestClient(create_omni_one_app(), raise_server_exceptions=False)


def test_root_redirects_to_close_pwa():
    client = _client()
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/close/"


def test_static_ui_is_served():
    client = _client()
    close = client.get("/close/")
    assert close.status_code == 200
    assert "Daily Close" in close.text

    seller = client.get("/seller.html")
    assert seller.status_code == 200
    assert "Seller OS" in seller.text


def test_api_still_responds_with_web_mount():
    client = _client()
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/openapi-tags").status_code == 200
