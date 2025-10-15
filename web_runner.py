import os, sys, threading, subprocess
from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

APP_VERSION = "r2"  # <-- cambia este valor en cada prueba (r2, r3, ...)

@app.get("/")
def health():
    return {"ok": True, "now_utc": str(datetime.utcnow()), "version": APP_VERSION}

@app.get("/test")
def test_send():
    import requests
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"ok": False, "error": "Faltan TELEGRAM_*"}, 500
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": "✅ Test desde Render OK"},
    )
    return {"ok": r.ok, "status": r.status_code, "resp": r.text}

def run_script():
    subprocess.Popen([sys.executable, "alerta_caucion_iol.py"], stdout=sys.stdout, stderr=sys.stderr)

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=run_script, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
