"""Flask entrypoint, Phase 2. Run from project root: python backend/app.py."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / '.env', override=False)

from api.routes import api_bp  # noqa: E402  .env must be loaded before initializing services


def create_app() -> Flask:
    app = Flask(__name__)
    # JSON is serialized as ASCII escape sequences for Windows PowerShell 5.1 compatibility.
    # JSON clients still decode the escapes back to original Vietnamese Unicode text.
    app.json.ensure_ascii = True
    app.register_blueprint(api_bp)
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host=os.getenv('FLASK_HOST', '127.0.0.1'),
            port=int(os.getenv('FLASK_PORT', '5000')), debug=False)
