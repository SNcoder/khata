"""Flask app factory for Site Khata."""

import os
import secrets
from datetime import timedelta

from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.exceptions import HTTPException

from database import SQLALCHEMY_DATABASE_URI, USE_PG, db, init_db

from .routes import api_bp

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# APP_PASSWORD set karo to login zaroori hoga; khali chodo to auth off (local dev)
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")


def create_app():
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
    # SECRET_KEY env var set karo warna har restart par sab sessions logout ho jaayenge
    app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    app.permanent_session_lifetime = timedelta(days=30)
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    app.register_blueprint(api_bp)

    @app.post("/api/login")
    def login():
        if not APP_PASSWORD:
            return jsonify({"ok": True})
        body = request.get_json(force=True)
        if secrets.compare_digest(body.get("password") or "", APP_PASSWORD):
            session.permanent = True
            session["authed"] = True
            return jsonify({"ok": True})
        return jsonify({"error": "Password galat hai"}), 401

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify({"ok": True})

    @app.before_request
    def require_auth():
        if (APP_PASSWORD
                and request.path.startswith("/api/")
                and request.path != "/api/login"
                and not session.get("authed")):
            return jsonify({"error": "Login required"}), 401

    @app.route("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "db": "postgresql" if USE_PG else "sqlite"})

    # API ko hamesha JSON error milna chahiye, HTML error page nahi
    @app.errorhandler(HTTPException)
    def handle_http_error(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": e.description}), e.code
        return e

    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        app.logger.exception(e)
        return jsonify({"error": "Server error — dobara try karo"}), 500

    with app.app_context():
        init_db()
    return app
