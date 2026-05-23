"""
Flask Application Factory
Wires together Flask, SocketIO, CORS, routes, the telemetry engine, and the DB.
"""
from flask import Flask, send_from_directory
from flask_socketio import SocketIO
from flask_cors import CORS
import os

from backend.config import Config
from backend.models.database import init_db
from backend.services.telemetry_engine import TelemetryEngine
from backend.routes.api import api_bp, set_engine as api_set_engine
from backend.routes.events import register_ws_events, set_engine as ws_set_engine

socketio = SocketIO()


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(__file__), "..", "frontend"),
        static_url_path="",
    )
    app.config.from_object(Config)

    # ── Extensions ────────────────────────────────────────────
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    socketio.init_app(app, cors_allowed_origins="*", async_mode="threading")

    # ── Database ──────────────────────────────────────────────
    init_db()

    # ── Telemetry engine (singleton) ──────────────────────────
    engine = TelemetryEngine()
    api_set_engine(engine)
    ws_set_engine(engine)

    # ── Blueprints ────────────────────────────────────────────
    app.register_blueprint(api_bp, url_prefix="/api")
    register_ws_events(socketio)

    # ── Serve frontend ────────────────────────────────────────
    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    return app
