import os, sys, threading, subprocess
from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

@app.get("/")
def health():
    return {"ok": True, "now_utc": str(datetime.utcnow())}

def run_script():
    # Lanza tu script principal en paralelo
    subprocess.Popen([sys.executable, "alerta_caucion_iol.py"], stdout=sys.stdout, stderr=sys.stderr)

if __name__ == "__main__":
    # Arranca el bot en background
    t = threading.Thread(target=run_script, daemon=True)
    t.start()

    # Levanta un server HTTP (Render lo necesita para Web Service)
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
