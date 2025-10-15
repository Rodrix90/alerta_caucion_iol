import os
import json
import time
import requests
from dataclasses import dataclass
from datetime import datetime, date
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

# ==========================
# Configuración y utilitarios
# ==========================
load_dotenv()

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

UMBRAL_10AM = 45.0   # > 45% alerta a las 10
UMBRAL_14HS = 80.0   # >= 80% alerta continua después de las 14

STATE_FILE = "estado_caucion.json"
HIGH_ALERT_JOB_ID = "high_alert_every_5m"

scheduler = BackgroundScheduler(timezone=TZ)

@dataclass
class EstadoCaucion:
    porcentaje: float
    timestamp: datetime

# ==========================
# Estado persistente en disco
# ==========================
def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "high_alert_active": False,
            "last_high_alert_start_date": None,  # YYYY-MM-DD
            "last_value": None
        }
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "high_alert_active": False,
            "last_high_alert_start_date": None,
            "last_value": None
        }

def save_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] No se pudo guardar estado: {e}")

# ==================================
# Envío de mensajes (Telegram)
# ==================================
def send_telegram(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("[WARN] Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en .env")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")

# ==================================
# Obtención del porcentaje en IOL
# ==================================
def fetch_caucion_percent() -> EstadoCaucion:
    """
    IMPLEMENTA AQUÍ tu lectura real de caución en IOL:
      - API autenticada (recomendado) o scraping con sesión autenticada.
    Debe retornar un float con el % de caución/margen usado.
    """
    # TODO: Reemplazar por la integración real con IOL
    simulated_value = leer_valor_simulado()
    return EstadoCaucion(porcentaje=float(simulated_value), timestamp=datetime.now(TZ))

def leer_valor_simulado() -> float:
    """
    Mientras integrás la consulta real, dejá un valor fijo o
    consultá tu propio endpoint. ÚTIL para probar la lógica.
    Cambiá este valor para simular distintos escenarios.
    """
    return 82.7  # Cambiá para probar (>80, <80, etc.)

# ==================================
# Lógica de notificaciones
# ==================================
def msg_estado(est: EstadoCaucion, prefijo="Estado"):
    ts = est.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    return f"{prefijo}: <b>{est.porcentaje:.2f}%</b> — {ts} (AR)"

def start_high_alerts():
    """Inicia (si no existe) el job cada 5 min para alta alerta."""
    if not scheduler.get_job(HIGH_ALERT_JOB_ID):
        scheduler.add_job(high_alert_tick, IntervalTrigger(minutes=5), id=HIGH_ALERT_JOB_ID)
        print("[INFO] Iniciadas alertas cada 5 minutos (≥ 80%).")

def stop_high_alerts():
    """Detiene el job de alta alerta si corre."""
    job = scheduler.get_job(HIGH_ALERT_JOB_ID)
    if job:
        job.remove()
        print("[INFO] Detenidas alertas cada 5 minutos.")

def check_and_alert_10am():
    """
    10:00 — Enviar estado. Si > 45% => Alerta.
    """
    state = load_state()
    est = fetch_caucion_percent()
    state["last_value"] = est.porcentaje
    save_state(state)

    # Estado diario 10:00
    send_telegram(f"📊 {msg_estado(est, 'Estado 10:00')}")

    # Alerta umbral 45
    if est.porcentaje > UMBRAL_10AM:
        send_telegram(f"⚠️ <b>Alerta 10:00</b>: {est.porcentaje:.2f}% (> {UMBRAL_10AM}%)")

def check_and_alert_14hs():
    """
    14:00 — Enviar estado. Si >= 80% => iniciar alertas cada 5 min.
    Si < 80% y venía activo el ciclo, se asegura que esté detenido.
    """
    state = load_state()
    est = fetch_caucion_percent()
    state["last_value"] = est.porcentaje
    save_state(state)

    # Estado 14:00
    send_telegram(f"📊 {msg_estado(est, 'Estado 14:00')}")

    # Manejo del ciclo >=80%
    if est.porcentaje >= UMBRAL_14HS:
        hoy = date.today().isoformat()
        if not state.get("high_alert_active"):
            start_high_alerts()
            state["high_alert_active"] = True
            state["last_high_alert_start_date"] = hoy
            save_state(state)
            send_telegram(
                f"🚨 <b>Umbral superado</b>: {est.porcentaje:.2f}% (≥ {UMBRAL_14HS}%). "
                f"Comienzan alertas cada 5 minutos."
            )
        else:
            send_telegram(f"🚨 <b>Se mantiene alto</b>: {est.porcentaje:.2f}% (≥ {UMBRAL_14HS}%).")
    else:
        if state.get("high_alert_active"):
            stop_high_alerts()
            state["high_alert_active"] = False
            save_state(state)
            send_telegram(
                f"✅ <b>Caución normalizada</b>: {est.porcentaje:.2f}% (< {UMBRAL_14HS}%). "
                f"Se detienen alertas cada 5 min."
            )

def high_alert_tick():
    """
    Job que corre cada 5 minutos DESPUÉS DE LAS 14 si >= 80%.
    Si baja de 80% => avisa y detiene el ciclo.
    """
    state = load_state()
    est = fetch_caucion_percent()
    state["last_value"] = est.porcentaje

    if est.porcentaje >= UMBRAL_14HS:
        send_telegram(
            f"🚨 <b>Caución alta</b>: {est.porcentaje:.2f}% (≥ {UMBRAL_14HS}%). "
            f"Sigo alertando cada 5 min."
        )
    else:
        stop_high_alerts()
        state["high_alert_active"] = False
        send_telegram(
            f"✅ <b>Caución normalizada</b>: {est.porcentaje:.2f}% (< {UMBRAL_14HS}%). "
            f"Se detienen alertas cada 5 min."
        )
    save_state(state)

# ==========================
# Programación de tareas
# ==========================
def main():
    state = load_state()
    # Por seguridad, detenemos el job de alta alerta al arrancar
    stop_high_alerts()
    state["high_alert_active"] = False
    save_state(state)

    # 10:00 AR — estado + alerta >45
    scheduler.add_job(
        check_and_alert_10am,
        CronTrigger(hour=10, minute=0),
        id="estado_10_am"
    )

    # 14:00 AR — estado + inicio ciclo >=80
    scheduler.add_job(
        check_and_alert_14hs,
        CronTrigger(hour=14, minute=0),
        id="estado_14_hs"
    )

    scheduler.start()
    print("[INFO] Scheduler iniciado. Ctrl+C para salir.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Saliendo...")
    finally:
        scheduler.shutdown(wait=False)

if __name__ == "__main__":
    main()