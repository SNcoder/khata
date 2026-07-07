"""
Site Khata — Material Management & Site Accounts
-------------------------------------------------
Backend  : backend/  (Python / Flask)
Database : database/ (PostgreSQL on Railway ya SQLite locally)
Frontend : frontend/ (HTML/CSS/JS)

LOCAL chalane ke liye:
    pip install -r requirements.txt
    python app.py
    Browser: http://localhost:5000

RAILWAY par automatically:
    DATABASE_URL environment variable se PostgreSQL connect hota hai
    Agar DATABASE_URL nahi mili to SQLite fallback ho jaata hai
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Site Khata chal raha hai → http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
