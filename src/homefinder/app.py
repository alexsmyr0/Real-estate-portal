from flask import Flask, jsonify
from .routes.health import health_bp


def _json_error(status_code: int, message: str):
    return jsonify(status="error", error={"code": status_code, "message": message}), status_code


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return "Hello World!"

    @app.errorhandler(400)
    def handle_bad_request(_error):
        return _json_error(400, "Bad Request")

    @app.errorhandler(401)
    def handle_unauthorized(_error):
        return _json_error(401, "Unauthorized")

    @app.errorhandler(403)
    def handle_forbidden(_error):
        return _json_error(403, "Forbidden")

    @app.errorhandler(404)
    def handle_not_found(_error):
        return _json_error(404, "Not Found")

    @app.errorhandler(500)
    def handle_internal_error(_error):
        return _json_error(500, "Internal Server Error")

    app.register_blueprint(health_bp)

    return app
