"""Minimal public orchestration service scaffold."""

from flask import Flask, jsonify


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health() -> tuple[dict[str, str], int]:
        return jsonify({"service": "eep", "status": "ok"}), 200

    return app


app = create_app()
