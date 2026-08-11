"""Bucle principal de orquestación y filtros de negocio."""
from __future__ import annotations
import logging
import time
import sys
import os
import json
import re
from datetime import datetime, timedelta, date
from config import VENUE_SERVICE_IDS, DEFAULT_CHECK_INTERVAL_SECONDS
from scraper import ColsubsidioScraper, SessionExpiredException
from notifier import TelegramNotifier

# Configurar logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("revisor_natacion")

# Caché en memoria para evitar recalcular los festivos del mismo año en cada escaneo
_holidays_cache: dict[int, set[date]] = {}

STATE_FILE = ".cooldown_state"
LAST_SLOTS_FILE = ".last_slots.json"

def load_cooldown_state() -> dict:
    """Carga el estado del orquestador en formato JSON para persistencia."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                try:
                    return json.loads(content)
                except ValueError:
                    # Compatibilidad con formato antiguo de float simple
                    return {
                        "last_expiry_alert_time": float(content),
                        "last_report_sent": "",
                        "last_processed_update_id": 0
                    }
        except Exception:
            pass
    return {
        "last_expiry_alert_time": 0.0,
        "last_report_sent": "",
        "last_processed_update_id": 0
    }

def save_cooldown_state(state: dict) -> None:
    """Guarda el estado del orquestador en formato JSON."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Error al guardar archivo de estado: %s", e)

def load_last_slots() -> dict[str, list[dict]]:
    """Carga los últimos slots detectados en la corrida anterior."""
    if os.path.exists(LAST_SLOTS_FILE):
        try:
            with open(LAST_SLOTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_last_slots(slots_dict: dict[str, list[dict]]) -> None:
    """Guarda los slots actuales detectados para comparación posterior."""
    try:
        with open(LAST_SLOTS_FILE, "w", encoding="utf-8") as f:
            json.dump(slots_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Error al guardar estado de slots: %s", e)

def find_new_slots(current_slots: list[dict], last_slots: list[dict]) -> list[dict]:
    """
    Compara los slots actuales contra los anteriores.
    Retorna los slots nuevos o los que tienen mayor número de cupos disponibles.
    """
    last_map = {(s["fecha"], s["hora"]): s["cupos"] for s in last_slots}
    new_slots = []
    for s in current_slots:
        key = (s["fecha"], s["hora"])
        if key not in last_map:
            new_slots.append(s)
        elif s["cupos"] > last_map[key]:
            new_slots.append(s)
    return new_slots

def is_colombian_holiday(target_date: date) -> bool:
    """Calcula dinámicamente si una fecha es festivo en Colombia usando la Ley Emiliani."""
    year = target_date.year
    if year not in _holidays_cache:
        # Algoritmo Meeus/Jones/Butcher para determinar el Domingo de Resurrección (Pascua)
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        L = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * L) // 451
        month = (h + L - 7 * m + 114) // 31
        day = ((h + L - 7 * m + 114) % 31) + 1
        easter = date(year, month, day)

        holidays = set()

        def add_emiliani(holiday_date: date):
            # Ley Emiliani: si no cae lunes, se mueve al lunes siguiente
            wd = holiday_date.weekday()
            if wd == 0:
                holidays.add(holiday_date)
            else:
                days_to_monday = 7 - wd
                holidays.add(holiday_date + timedelta(days=days_to_monday))

        # 1. Festivos con fecha fija (no sujetos a Ley Emiliani)
        holidays.add(date(year, 1, 1))    # Año Nuevo
        holidays.add(date(year, 5, 1))    # Día del Trabajo
        holidays.add(date(year, 7, 20))   # Grito de Independencia
        holidays.add(date(year, 8, 7))    # Batalla de Boyacá
        holidays.add(date(year, 12, 8))   # Inmaculada Concepción
        holidays.add(date(year, 12, 25))  # Navidad

        # 2. Festivos con fecha fija trasladables (Ley Emiliani)
        add_emiliani(date(year, 1, 6))    # Reyes Magos
        add_emiliani(date(year, 3, 19))   # San José
        add_emiliani(date(year, 6, 29))   # San Pedro y San Pablo
        add_emiliani(date(year, 8, 15))   # Asunción de la Virgen
        add_emiliani(date(year, 10, 12))  # Día de la Raza
        add_emiliani(date(year, 11, 1))   # Todos los Santos
        add_emiliani(date(year, 11, 11))  # Independencia de Cartagena

        # 3. Festivos relacionados con Pascua (fechas móviles sin Emiliani)
        holidays.add(easter - timedelta(days=3))  # Jueves Santo
        holidays.add(easter - timedelta(days=2))  # Viernes Santo

        # 4. Festivos relacionados con Pascua trasladables (Ley Emiliani)
        # Ascensión (40 días después de Pascua, siempre cae jueves -> se mueve a lunes = Pascua + 43 días)
        # Corpus Christi (60 días después de Pascua, siempre cae jueves -> se mueve a lunes = Pascua + 64 días)
        # Sagrado Corazón (68 días después de Pascua, siempre cae viernes -> se mueve a lunes = Pascua + 71 días)
        holidays.add(easter + timedelta(days=43))  # Ascensión
        holidays.add(easter + timedelta(days=64))  # Corpus Christi
        holidays.add(easter + timedelta(days=71))  # Sagrado Corazón

        _holidays_cache[year] = holidays

    return target_date in _holidays_cache[year]

def is_within_preferred_schedule(date_str: str, time_str: str) -> bool:
    """
    Evalúa si la fecha y hora corresponden a las preferencias del usuario:
    - Sábados, Domingos y Festivos colombianos: Cualquier horario.
    - Lunes a Viernes no festivos: Hora de inicio entre las 18:00 y las 20:00.
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_of_week = dt.weekday()  # 0 es Lunes, 6 es Domingo
        
        # Si es fin de semana (sábado/domingo) o es día festivo
        if day_of_week >= 5 or is_colombian_holiday(dt.date()):
            return True
        else:
            # Lunes a Viernes normal
            hour = int(time_str.split(":")[0])
            return 18 <= hour <= 20
    except Exception as e:
        logger.error("Error al evaluar horario preferido (%s, %s): %s", date_str, time_str, e)
        return False

def check_venues(scraper: ColsubsidioScraper, notifier: TelegramNotifier, force_send: bool = False) -> None:
    """
    Consulta la disponibilidad para todas las sedes configuradas.
    - force_send=True: Envía el reporte completo sin importar si hay delta de cupos.
    - force_send=False: Envía el reporte solo si hay cupos nuevos detectados.
    """
    last_slots_dict = load_last_slots()
    current_slots_dict = {}

    for venue_name, service_id in VENUE_SERVICE_IDS.items():
        try:
            logger.info("Chequeando disponibilidad para la sede: %s (ID: %s)", venue_name, service_id)
            available_dates = scraper.fetch_available_dates(service_id)
            
            matching_slots = []
            for date_str in available_dates:
                slots = scraper.fetch_slots_for_date(service_id, date_str)
                for slot in slots:
                    if is_within_preferred_schedule(slot["fecha"], slot["hora"]):
                        matching_slots.append(slot)
            
            current_slots_dict[venue_name] = matching_slots
            
            if matching_slots:
                last_venue_slots = last_slots_dict.get(venue_name, [])
                new_slots = find_new_slots(matching_slots, last_venue_slots)
                
                # Reportar si es envío programado (force_send) o si hay cupos nuevos
                if force_send or new_slots:
                    # Pasamos force=force_send para que el notificador se salte la caché interna en reportes programados
                    notified = notifier.notify_venue_slots(venue_name, matching_slots, force=force_send)
                    if notified:
                        logger.info("¡Reporte enviado para la sede %s (force_send=%s)!", venue_name, force_send)
        except SessionExpiredException:
            raise
        except Exception as e:
            logger.error("Error al escanear la sede %s: %s", venue_name, e)

    save_last_slots(current_slots_dict)

def main() -> None:
    """Bucle principal de ejecución del Revisor de Natación."""
    logger.info("Iniciando el Revisor de Natación Colsubsidio...")
    
    scraper = ColsubsidioScraper()
    notifier = TelegramNotifier()
    
    interval = DEFAULT_CHECK_INTERVAL_SECONDS
    state = load_cooldown_state()

    # 1. Procesar comandos interactivos de Telegram antes de hacer el chequeo
    offset = state.get("last_processed_update_id", 0) + 1
    updates = notifier.get_incoming_commands(offset=offset)

    for update in updates:
        update_id = update.get("update_id")
        if update_id:
            state["last_processed_update_id"] = max(state["last_processed_update_id"], update_id)

        message = update.get("message", {})
        text = message.get("text", "").strip()
        chat_id = message.get("chat", {}).get("id")

        # Seguridad: Solo procesar comandos del chat_id autorizado
        if str(chat_id) != str(notifier.chat_id):
            continue

        # Match del comando de agendamiento (/agendar_ID_YYYY_MM_DD_HH_MM)
        match = re.match(r"^/agendar_(\d+)_(\d{4}_\d{2}_\d{2})_(\d{2}_\d{2})$", text)
        if match:
            service_id = int(match.group(1))
            date_str = match.group(2).replace("_", "-")
            time_str = match.group(3).replace("_", ":")

            from config import VENUE_SERVICE_IDS, COLSUBSIDIO_TIQUETERA_ID
            sede_name = next((k for k, v in VENUE_SERVICE_IDS.items() if v == service_id), "Desconocida")

            logger.info("Comando de agendamiento recibido para: %s, %s, %s", sede_name, date_str, time_str)
            notifier.send_message(f"⏳ *[Procesando Reserva]*\n\nSede: *{sede_name}*\nFecha: *{date_str}*\nHora: *{time_str}*\nUsando tiquetera: `{COLSUBSIDIO_TIQUETERA_ID}`\n\nPor favor espera...")

            if not COLSUBSIDIO_TIQUETERA_ID:
                notifier.send_message("❌ *Error al agendar:* No se encuentra configurado el ID de tiquetera (`COLSUBSIDIO_TIQUETERA_ID`).")
                continue

            success, msg = scraper.book_slot(service_id, date_str, time_str, COLSUBSIDIO_TIQUETERA_ID)
            if success:
                notifier.send_message(
                    "🎉 *¡Reserva Realizada con Éxito!* 🎉\n\n"
                    f"📍 *Sede:* {sede_name}\n"
                    f"📅 *Fecha:* {date_str}\n"
                    f"⏰ *Hora:* {time_str}\n"
                    "🎟️ *Confirmación:* La reserva ha sido ingresada en la plataforma Colsubsidio."
                )
            else:
                notifier.send_message(
                    "⚠️ *Fallo al Reservar* ⚠️\n\n"
                    f"📍 *Sede:* {sede_name}\n"
                    f"📅 *Fecha:* {date_str}\n"
                    f"⏰ *Hora:* {time_str}\n"
                    f"❌ *Motivo:* `{msg}`"
                )

    # 2. Calcular hora local de Colombia (Bogotá UTC-5)
    now_colombia = datetime.utcnow() - timedelta(hours=5)
    date_str = now_colombia.strftime("%Y-%m-%d")
    hour = now_colombia.hour

    is_scheduled_time = hour in [6, 13]
    report_key = f"{date_str}-{hour}"

    send_full_report = False
    if is_scheduled_time and state.get("last_report_sent") != report_key:
        send_full_report = True

    # Permitir forzar el reporte completo usando el argumento --force
    force_run = "--force" in sys.argv
    if force_run:
        send_full_report = True

    once = "--once" in sys.argv

    if once:
        try:
            check_venues(scraper, notifier, force_send=send_full_report)
            if send_full_report:
                state["last_report_sent"] = report_key
            save_cooldown_state(state)
            logger.info("Chequeo único finalizado con éxito.")
        except SessionExpiredException as e:
            logger.error("La sesión de Colsubsidio ha expirado: %s", e)
            refreshed = False
            try:
                logger.info("Intentando auto-sanar: extrayendo nuevas cookies del navegador...")
                sys.path.append(os.path.dirname(__file__))
                from get_cookies import extract_colsubsidio_cookies, update_env_file
                cookies = extract_colsubsidio_cookies()
                if "sistema" in cookies and "Csrf-Token" in cookies:
                    update_env_file(cookies)
                    cookie_val = cookies["sistema"]
                    csrf_val = cookies["Csrf-Token"]
                    
                    scraper.session.cookies.set("sistema", cookie_val, domain="www.diversioncolsubsidio.com")
                    scraper.session.cookies.set("sistema", cookie_val, domain=".diversioncolsubsidio.com")
                    scraper.session.cookies.set("sitio", cookie_val, domain="www.diversioncolsubsidio.com")
                    scraper.session.cookies.set("sitio", cookie_val, domain=".diversioncolsubsidio.com")
                    scraper.session.cookies.set("Csrf-Token", csrf_val, domain="www.diversioncolsubsidio.com")
                    scraper.session.cookies.set("Csrf-Token", csrf_val, domain=".diversioncolsubsidio.com")
                    
                    logger.info("Cookies refrescadas con exito desde el navegador. Reintentando chequeo...")
                    check_venues(scraper, notifier, force_send=send_full_report)
                    if send_full_report:
                        state["last_report_sent"] = report_key
                    save_cooldown_state(state)
                    refreshed = True
                    logger.info("Chequeo único finalizado con éxito tras auto-sanación.")
            except Exception as ex:
                logger.error("Fallo durante el intento de auto-sanar cookies: %s", ex)

            if not refreshed:
                current_time = time.time()
                if current_time - state["last_expiry_alert_time"] > 86400:
                    msg = (
                        "⚠️ *[Alerta de Revisor de Natación]*\n\n"
                        "Tu sesión de Colsubsidio (cookie `sistema`) ha expirado o es inválida.\n"
                        "Por favor, abre la web de Colsubsidio en tu navegador para renovarla."
                    )
                    if notifier.send_message(msg):
                        state["last_expiry_alert_time"] = current_time
                        save_cooldown_state(state)
                        logger.info("Alerta de sesión expirada enviada a Telegram.")
                sys.exit(0)
        except Exception as e:
            logger.error("Error inesperado en la ejecución única: %s", e)
            sys.exit(1)
        return

    while True:
        try:
            check_venues(scraper, notifier, force_send=send_full_report)
            if send_full_report:
                state["last_report_sent"] = report_key
            save_cooldown_state(state)
            logger.info("Chequeo finalizado. Durmiendo por %s segundos...", interval)
        except SessionExpiredException as e:
            logger.error("La sesión de Colsubsidio ha expirado: %s", e)
            refreshed = False
            try:
                logger.info("Intentando auto-sanar: extrayendo nuevas cookies del navegador...")
                sys.path.append(os.path.dirname(__file__))
                from get_cookies import extract_colsubsidio_cookies, update_env_file
                cookies = extract_colsubsidio_cookies()
                if "sistema" in cookies and "Csrf-Token" in cookies:
                    update_env_file(cookies)
                    cookie_val = cookies["sistema"]
                    csrf_val = cookies["Csrf-Token"]
                    
                    scraper.session.cookies.set("sistema", cookie_val, domain="www.diversioncolsubsidio.com")
                    scraper.session.cookies.set("sistema", cookie_val, domain=".diversioncolsubsidio.com")
                    scraper.session.cookies.set("sitio", cookie_val, domain="www.diversioncolsubsidio.com")
                    scraper.session.cookies.set("sitio", cookie_val, domain=".diversioncolsubsidio.com")
                    scraper.session.cookies.set("Csrf-Token", csrf_val, domain="www.diversioncolsubsidio.com")
                    scraper.session.cookies.set("Csrf-Token", csrf_val, domain=".diversioncolsubsidio.com")
                    
                    logger.info("Cookies refrescadas con exito desde el navegador. Reintentando chequeo...")
                    check_venues(scraper, notifier, force_send=send_full_report)
                    if send_full_report:
                        state["last_report_sent"] = report_key
                    save_cooldown_state(state)
                    refreshed = True
            except Exception as ex:
                logger.error("Fallo durante el intento de auto-sanar cookies: %s", ex)

            if not refreshed:
                current_time = time.time()
                if current_time - state["last_expiry_alert_time"] > 86400:
                    msg = (
                        "⚠️ *[Alerta de Revisor de Natación]*\n\n"
                        "Tu sesión de Colsubsidio (cookie `sistema`) ha expirado o es inválida.\n"
                        "Por favor, abre la web de Colsubsidio en tu navegador para renovarla "
                        "y deja el revisor corriendo localmente para que se sincronice solo."
                    )
                    if notifier.send_message(msg):
                        state["last_expiry_alert_time"] = current_time
                        save_cooldown_state(state)
                        logger.info("Alerta de sesión expirada enviada a Telegram.")
        except Exception as e:
            logger.error("Error inesperado en el loop principal: %s", e)

        # Volver a cargar el estado en cada iteración del bucle continuo para refrescar variables
        state = load_cooldown_state()
        time.sleep(interval)

if __name__ == "__main__":
    main()
