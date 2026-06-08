"""Bucle principal de orquestación y filtros de negocio."""
from __future__ import annotations
import logging
import time
import sys
import os
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

def check_venues(scraper: ColsubsidioScraper, notifier: TelegramNotifier) -> None:
    """Consulta la disponibilidad para todas las sedes configuradas y dispara alertas compiladas."""
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
            
            if matching_slots:
                notified = notifier.notify_venue_slots(venue_name, matching_slots)
                if notified:
                    logger.info("¡Alerta compilada enviada para la sede %s!", venue_name)
        except SessionExpiredException:
            # Propagar para que el loop principal lo capture y alerte al usuario
            raise
        except Exception as e:
            logger.error("Error al escanear la sede %s: %s", venue_name, e)

def main() -> None:
    """Bucle principal de ejecución periódica o única."""
    logger.info("Iniciando el Revisor de Natación Colsubsidio...")
    
    scraper = ColsubsidioScraper()
    notifier = TelegramNotifier()
    
    interval = DEFAULT_CHECK_INTERVAL_SECONDS
    state_file = ".cooldown_state"
    last_expiry_alert_time = 0.0

    # Intentar cargar el estado anterior del cooldown
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                last_expiry_alert_time = float(f.read().strip())
        except Exception:
            pass

    once = "--once" in sys.argv

    if once:
        try:
            check_venues(scraper, notifier)
            logger.info("Chequeo único finalizado con éxito.")
        except SessionExpiredException as e:
            logger.error("La sesión de Colsubsidio ha expirado: %s", e)
            current_time = time.time()
            if current_time - last_expiry_alert_time > 86400:
                msg = (
                    "⚠️ *[Alerta de Revisor de Natación]*\n\n"
                    "Tu sesión de Colsubsidio (cookie `sistema`) ha expirado o es inválida.\n"
                    "Por favor, inicia sesión en la web, extrae la nueva cookie e insértala "
                    "en tus variables de entorno para continuar con el monitoreo."
                )
                if notifier.send_message(msg):
                    last_expiry_alert_time = current_time
                    try:
                        with open(state_file, "w") as f:
                            f.write(str(last_expiry_alert_time))
                    except Exception:
                        pass
                    logger.info("Alerta de sesión expirada enviada a Telegram.")
            sys.exit(1)
        except Exception as e:
            logger.error("Error inesperado en la ejecución única: %s", e)
            sys.exit(1)
        return

    while True:
        try:
            check_venues(scraper, notifier)
            logger.info("Chequeo finalizado. Durmiendo por %s segundos...", interval)
        except SessionExpiredException as e:
            logger.error("La sesión de Colsubsidio ha expirado: %s", e)
            current_time = time.time()
            # Cooldown de 24 horas para alertas de expiración (86400 segundos)
            if current_time - last_expiry_alert_time > 86400:
                msg = (
                    "⚠️ *[Alerta de Revisor de Natación]*\n\n"
                    "Tu sesión de Colsubsidio (cookie `sistema`) ha expirado o es inválida.\n"
                    "Por favor, inicia sesión en la web, extrae la nueva cookie e insértala "
                    "en tus variables de entorno para continuar con el monitoreo."
                )
                if notifier.send_message(msg):
                    last_expiry_alert_time = current_time
                    try:
                        with open(state_file, "w") as f:
                            f.write(str(last_expiry_alert_time))
                    except Exception:
                        pass
                    logger.info("Alerta de sesión expirada enviada a Telegram.")
        except Exception as e:
            logger.error("Error inesperado en el loop principal: %s", e)
        
        time.sleep(interval)

if __name__ == "__main__":
    main()
