from flask import Flask
from .config import Settings, load_settings
from flask import Flask, jsonify
from .routes.health import health_bp


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or load_settings()

def _json_error(status_code: int, message: str):
    return jsonify(status="error", error={"code": status_code, "message": message}), status_code


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or load_settings()
    app = Flask(__name__)
    app.config.update(
        APP_HOST=settings.app_host,
        APP_PORT=settings.app_port,
        APP_DEBUG=settings.debug,
        DEBUG=settings.debug,
        DB_SCHEME=settings.db_scheme,
        DB_HOST=settings.db_host,
        DB_PORT=settings.db_port,
        DB_NAME=settings.db_name,
        DB_USER=settings.db_user,
        DB_PASSWORD=settings.db_password,
        DATABASE_URL=settings.database_url,
    )

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
