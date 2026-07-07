"""Flask app factory for Site Khata."""

import os

from flask import Flask, jsonify, send_from_directory

from database import USE_PG, close_db, init_db

from .routes import api_bp

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


def create_app():
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
    app.register_blueprint(api_bp)
    app.teardown_appcontext(close_db)

    @app.route("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "db": "postgresql" if USE_PG else "sqlite"})

    init_db()
    return app
