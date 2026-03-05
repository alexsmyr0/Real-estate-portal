from flask import Flask
from .routes.health import health_bp


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return "Hello World!"

    app.register_blueprint(health_bp)

    return app
