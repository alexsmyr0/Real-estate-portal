import pytest
from flask import abort

from homefinder.app import create_app


@pytest.fixture()
def client():
    app = create_app()
    app.config.update(TESTING=False, PROPAGATE_EXCEPTIONS=False)

    @app.get("/api/v1/_test-error")
    def raise_error():
        raise RuntimeError("boom")

    @app.get("/api/v1/_test-400")
    def raise_400():
        abort(400)

    @app.get("/api/v1/_test-401")
    def raise_401():
        abort(401)

    @app.get("/api/v1/_test-403")
    def raise_403():
        abort(403)

    with app.test_client() as test_client:
        yield test_client


def test_unknown_route_returns_json_404(client):
    response = client.get("/api/v1/unknown-route")

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json() == {
        "status": "error",
        "error": {"code": 404, "message": "Not Found"},
    }


def test_internal_error_returns_json_500(client):
    response = client.get("/api/v1/_test-error")

    assert response.status_code == 500
    assert response.is_json
    assert response.get_json() == {
        "status": "error",
        "error": {"code": 500, "message": "Internal Server Error"},
    }


@pytest.mark.parametrize(
    ("path", "status_code", "message"),
    [
        ("/api/v1/_test-400", 400, "Bad Request"),
        ("/api/v1/_test-401", 401, "Unauthorized"),
        ("/api/v1/_test-403", 403, "Forbidden"),
    ],
)
def test_client_errors_return_json(path, status_code, message, client):
    response = client.get(path)

    assert response.status_code == status_code
    assert response.is_json
    assert response.get_json() == {
        "status": "error",
        "error": {"code": status_code, "message": message},
    }
