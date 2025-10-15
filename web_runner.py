import os, sys, threading, subprocess
from flask import Flask
from datetime import datetime

app = Flask(__name__)

APP_VERSION = "r3"  # marcador visible en "/"

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

# ---- importar funciones del script principal ----
from alerta_caucion_iol import (
    chequear_alertas_10am,
    chequear_alertas_14pm,
    chequeo_cada_5_min_si_80,
)

@app.get("/run/10")
def run_10():
    chequear_alertas_10am()
    return {"ok": True, "ran": "10am"}

@app.get("/run/14")
def run_14():
    chequear_alertas_14pm()
    return {"ok": True, "ran": "14pm"}

@app.get("/run/5m")
def run_5m():
    chequeo_cada_5_min_si_80()
    return {"ok": True, "ran": "5min-check"}

@app.get("/routes")
def routes():
    return {"routes": [str(r) for r in app.url_map.iter_rules()]}

def run_script_background():
    # Lanza tu script con el scheduler (se ejecuta solo por el bloque __main__ del script)
    subprocess.Popen([sys.executable, "alerta_caucion_iol.py"], stdout=sys.stdout, stderr=sys.stderr)

if __name__ == "__main__":
    # Arranca el bot de fondo (scheduler real)
    t = threading.Thread(target=run_script_background, daemon=True)
    t.start()
    # Server HTTP para Render
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
