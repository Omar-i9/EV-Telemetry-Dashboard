"""
Entry Point — run with:  python run.py
"""
from backend.app import create_app, socketio
from backend.config import Config

if __name__ == "__main__":
    app = create_app()
    print(f"""
  ╔══════════════════════════════════════════╗
  ║   EV TELEMETRY DASHBOARD  v1.0           ║
  ║   http://{Config.HOST}:{Config.PORT}                  ║
  ║   WebSocket enabled — live data ready    ║
  ╚══════════════════════════════════════════╝
""")
    socketio.run(app, host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, allow_unsafe_werkzeug=True)