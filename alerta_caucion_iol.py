import os, json, time, math
from datetime import datetime
import requests
from apscheduler.schedulers.background import BackgroundScheduler

TZ = "America/Argentina/Buenos_Aires"
STATE_PATH = "estado_caucion.json"

# ---------- Utilidades de estado ----------
def _load_state():
    if not os.path.exists(STATE_PATH):
        return {"modo_80": False, "ultimo_porcentaje": None}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"modo_80": False, "ultimo_porcentaje": None}

def _save_state(s):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

# ---------- Telegram ----------
def send_telegram(text):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat  = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat, "text": text})
    # si falla, logueamos breve
    if not r.ok:
        print("TELEGRAM_ERROR", r.status_code, r.text)

# ---------- Fuente de datos (IOL) ----------
def get_porcentaje_caucion():
    """
    TODO: Implementar integración real con IOL.
    Sugerencia: usar requests con un endpoint/HTML de IOL (API o scraping), parsear, y devolver float.
    Debe devolver el porcentaje actual, p.ej. 63.5
    """
    # Modo DEMO para validar lógica end-to-end sin IOL:
    # Activá con env: USE_DUMMY=1 y (opcional) DUMMY_PATTERN=45,82,83,79,78 (ciclo)
    if os.environ.get("USE_DUMMY") == "1":
        pattern = os.environ.get("DUMMY_PATTERN", "42,46,81,83,78,77,82,79,60,44")
        valores = [float(x.strip()) for x in pattern.split(",") if x.strip()]
        # Elegimos un valor en función del minuto para que vaya rotando
        idx = int(datetime.now().strftime("%M")) % len(valores)
        return valores[idx]
    raise NotImplementedError("Implementa get_porcentaje_caucion() con API/scraping de IOL")

# ---------- Lógica de negocio ----------
def enviar_resumen(prefix, p):
    send_telegram(f"📈 {prefix}: {p:.2f}% (IOL)")

def chequear_alertas_10am():
    p = get_porcentaje_caucion()
    s = _load_state()
    s["ultimo_porcentaje"] = p
    _save_state(s)
    enviar_resumen("Caución (10:00)", p)
    if p > 45:
        send_telegram(f"⚠️ Alerta: {p:.2f}% > 45%")

def chequear_alertas_14pm():
    p = get_porcentaje_caucion()
    s = _load_state()
    s["ultimo_porcentaje"] = p
    _save_state(s)
    enviar_resumen("Caución (14:00)", p)
    if p > 80 and not s.get("modo_80"):
        s["modo_80"] = True
        _save_state(s)
        send_telegram(f"🚨 Alerta: {p:.2f}% > 80% — activo alertas cada 5 minutos")

def chequeo_cada_5_min_si_80():
    s = _load_state()
    if not s.get("modo_80"):
        return  # inactivo: no hacemos nada
    p = get_porcentaje_caucion()
    s["ultimo_porcentaje"] = p
    if p > 80:
        _save_state(s)
        # envío recurrente
        send_telegram(f"⏰ Sigue >80%: {p:.2f}%")
    else:
        s["modo_80"] = False
        _save_state(s)
        send_telegram(f"✅ Normalizado: {p:.2f}% (<80%). Detengo alertas de 5 min.")

# ---------- Scheduler ----------
def start_scheduler():
    sched = BackgroundScheduler(timezone=TZ)

    # 10:00 AR
    sched.add_job(chequear_alertas_10am, "cron", hour=10, minute=0)

    # 14:00 AR
    sched.add_job(chequear_alertas_14pm, "cron", hour=14, minute=0)

    # Cada 5 min a partir de 14:00 AR (se enviará solo si modo_80==True)
    sched.add_job(chequeo_cada_5_min_si_80, "cron", hour=14, minute="*/5")

    sched.start()
    return sched

# Si se ejecuta directo (local o en Render vía web_runner)
if __name__ == "__main__":
    send_telegram("🤖 Bot de cauciones iniciado")
    start_scheduler()
    # Mantener vivo si se corre standalone
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pass
