# Diseño Técnico: Orquestador y Filtros de Monitoreo (`monitor_orchestrator`)

Este documento describe el flujo del bucle principal y la lógica de filtrado de horarios.

---

## 1. Algoritmo de Orquestación

La lógica principal residirá en [main.py](file:///g:/Mi%20unidad/Natacion%20Colsubsidio/code/main.py).

```python
import time
import logging
from datetime import datetime
from config import VENUE_SERVICE_IDS, DEFAULT_CHECK_INTERVAL_SECONDS
from scraper import ColsubsidioScraper, SessionExpiredException
from notifier import TelegramNotifier

logger = logging.getLogger(__name__)

def is_within_preferred_schedule(date_str: str, time_str: str) -> bool:
    """
    Evalúa si la fecha y hora corresponden a las preferencias del usuario:
    - Lunes a Viernes (0-4): Hora de inicio entre las 18:00 y las 20:00.
    - Sábados y Domingos (5-6): Cualquier horario.
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_of_week = dt.weekday()  # 0 es Lunes, 6 es Domingo
        
        if day_of_week < 5:  # Entre semana
            hour = int(time_str.split(":")[0])
            return 18 <= hour <= 20
        else:  # Fin de semana
            return True
    except Exception as e:
        logger.error("Error al evaluar horario preferido (%s, %s): %s", date_str, time_str, e)
        return False

def check_venues(scraper: ColsubsidioScraper, notifier: TelegramNotifier) -> None:
    """Consulta la disponibilidad para todas las sedes y dispara alertas."""
    for venue_name, service_id in VENUE_SERVICE_IDS.items():
        try:
            available_dates = scraper.fetch_available_dates(service_id)
            for date_str in available_dates:
                slots = scraper.fetch_slots_for_date(service_id, date_str)
                for slot in slots:
                    if is_within_preferred_schedule(slot["fecha"], slot["hora"]):
                        # Intentar notificar (el notificador se encargará de omitir duplicados)
                        notifier.notify_slot(
                            venue=venue_name,
                            date_str=slot["fecha"],
                            time_str=slot["hora"],
                            slots=slot["cupos"]
                        )
        except SessionExpiredException as e:
            logger.error("Sesión expirada para Colsubsidio en la sede %s: %s", venue_name, e)
            raise  # Se propaga para ser manejada en el bucle principal (con cooldown)
        except Exception as e:
            logger.error("Error inesperado escaneando la sede %s: %s", venue_name, e)
```

---

## 2. Manejo de Alertas de Sesión Expirada

*   Cuando se atrapa `SessionExpiredException`, el bucle principal llamará a un método especial para notificar al usuario.
*   Para evitar el envío repetitivo de esta alerta (spam en Telegram si la sesión se vence a mitad de la noche), se almacenará la marca de tiempo de la última notificación de expiración:
    `last_session_expired_alert: float = 0.0`
*   Solo se enviará el mensaje si `time.time() - last_session_expired_alert > 86400` (24 horas).

---

## 3. Alternativas Descartadas

*   **Alternativa Descartada:** Detener el script por completo si la sesión expira.
    *   *Razón:* Si la sesión expira, queremos que el script continúe corriendo y reintentando (en caso de que el usuario actualice la variable de entorno o la sesión vuelva a ser válida tras un reinicio de contenedores) en lugar de morir por completo (respetando la **Regla de Oro 2: Robustez**).
