"""Flask app factory for Site Khata."""

import os
import secrets
from datetime import timedelta

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from database import SQLALCHEMY_DATABASE_URI, USE_PG, db, init_db
from database.auth_models import seed_auth

from .admin_routes import admin_bp
from .auth import auth_bp, load_current_user
from .routes import api_bp

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Pehli baar chalne par is email/password se admin user banta hai (baaki sab
# users invite email se apna password khud set karte hain). Login ke baad
# Admin Panel se ye password zaroor badlo.
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@sitekhata.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


def create_app():
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
    # SECRET_KEY env var set karo warna har restart par sab sessions logout ho jaayenge
    app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    app.permanent_session_lifetime = timedelta(days=30)
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    # Har /api/ request par session user load + login check (auth.py)
    app.before_request(load_current_user)

    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

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
        if seed_auth(ADMIN_EMAIL, ADMIN_PASSWORD):
            print(f"Default admin user bana: '{ADMIN_EMAIL}' — pehla login karke password badlo!")
    return app
