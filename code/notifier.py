"""Módulo encargado de las alertas y comunicación con Telegram."""
from __future__ import annotations
import logging
import time
from datetime import datetime
import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, ALERT_CACHE_DURATION_SECONDS

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Clase para enviar alertas a un chat de Telegram con control de de-duplicación."""

    def __init__(
        self,
        token: str | None = None,
        chat_id: str | None = None,
        cache_duration_seconds: int = ALERT_CACHE_DURATION_SECONDS
    ) -> None:
        """Inicializa el notificador con credenciales explícitas o de configuración."""
        self.token = token or TELEGRAM_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.cache_duration_seconds = cache_duration_seconds
        # Estructura de caché: { "sede:fecha:hora:cupos": epoch_timestamp }
        self._sent_alerts: dict[str, float] = {}

    def _generate_key(self, venue: str, date_str: str, time_str: str, slots: int) -> str:
        """Genera una clave única de-duplicada para identificar un cupo específico."""
        return f"{venue.strip().upper()}:{date_str.strip()}:{time_str.strip()}:{slots}"

    def prune_cache(self) -> None:
        """Elimina alertas de la caché que superen el tiempo de expiración."""
        now = time.time()
        expired_keys = [
            key for key, timestamp in self._sent_alerts.items()
            if now - timestamp > self.cache_duration_seconds
        ]
        for key in expired_keys:
            del self._sent_alerts[key]

    def send_message(self, text: str) -> bool:
        """
        Envía un mensaje de texto simple formateado en Markdown a Telegram.
        Retorna True si fue exitoso, False en caso contrario.
        """
        if not self.token or not self.chat_id:
            logger.error(
                "No se puede enviar el mensaje de Telegram: token o chat_id no configurados."
            )
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("Mensaje enviado con éxito a Telegram.")
                return True
            else:
                logger.warning(
                    "Error al enviar mensaje a Telegram (HTTP %s): %s",
                    response.status_code,
                    response.text
                )
                return False
        except requests.RequestException as e:
            logger.warning("Fallo en la conexión HTTP con la API de Telegram: %s", e)
            return False

    def get_incoming_commands(self, offset: int = 0) -> list[dict]:
        """
        Consulta la API de Telegram getUpdates para obtener los mensajes del bot.
        Retorna la lista de resultados de actualizaciones.
        """
        if not self.token:
            logger.error("No se puede obtener comandos de Telegram: token no configurado.")
            return []

        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        payload = {
            "offset": offset,
            "timeout": 0,
            "allowed_updates": ["message"]
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return response.json().get("result", [])
            else:
                logger.warning(
                    "Error al obtener actualizaciones de Telegram (HTTP %s): %s",
                    response.status_code,
                    response.text
                )
                return []
        except Exception as e:
            logger.warning("Fallo al conectarse con getUpdates de Telegram: %s", e)
            return []

    def notify_slot(self, venue: str, date_str: str, time_str: str, slots: int) -> bool:
        """
        Envía una alerta de cupo disponible si no ha sido notificada recientemente.
        Retorna True si la alerta se envió por primera vez con éxito, False de lo contrario.
        """
        self.prune_cache()
        key = self._generate_key(venue, date_str, time_str, slots)

        # Verificar si ya está en caché
        if key in self._sent_alerts:
            logger.debug("Alerta duplicada omitida para el cupo: %s", key)
            return False

        # Construir mensaje Markdown
        message = (
            "🏊 *¡Cupos Libres de Natación!*\n\n"
            f"📍 *Sede:* {venue}\n"
            f"📅 *Fecha:* {date_str}\n"
            f"⏰ *Hora:* {time_str}\n"
            f"🎟️ *Cupos disponibles:* `{slots}`\n\n"
            "🔗 _Reserva en la Tienda de Diversión Colsubsidio_"
        )

        success = self.send_message(message)
        if success:
            self._sent_alerts[key] = time.time()
            return True

        return False

    def notify_venue_slots(self, venue: str, slots: list[dict], force: bool = False) -> bool:
        """
        Envía un único mensaje compilado con todos los cupos de una sede.
        Evita enviar si el estado de disponibilidad no ha cambiado (a menos que force sea True).
        """
        if not slots:
            return False

        # Ordenar slots por fecha y hora para consistencia
        sorted_slots = sorted(slots, key=lambda x: (x["fecha"], x["hora"]))

        # Generar clave única para de-duplicación basada en todos los slots de esta sede
        # Formato de clave: VENUE|fecha:hora:cupos|fecha:hora:cupos|...
        slot_strings = [f"{s['fecha']}:{s['hora']}:{s['cupos']}" for s in sorted_slots]
        key = f"{venue.strip().upper()}|" + "|".join(slot_strings)

        self.prune_cache()

        # Verificar si ya se envió exactamente esta configuración recientemente
        if not force and key in self._sent_alerts:
            logger.debug("Alerta compilada duplicada omitida para la sede: %s", venue)
            return False

        # Construir el mensaje agrupando por fecha
        from collections import defaultdict
        grouped = defaultdict(list)
        for s in sorted_slots:
            grouped[s["fecha"]].append(s)

        lines = [
            "🏊 *¡Cupos Libres de Natación!*",
            f"📍 *Sede:* {venue}\n"
        ]

        from config import VENUE_SERVICE_IDS
        service_id = VENUE_SERVICE_IDS.get(venue.strip().upper(), 0)

        for date_str, date_slots in sorted(grouped.items()):
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                day_name = dias[dt.weekday()]
                date_header = f"📅 *{day_name} {date_str}:*"
            except Exception:
                date_header = f"📅 *{date_str}:*"

            lines.append(date_header)
            for s in date_slots:
                # Generar link interactivo de comando para Telegram (ej. /agendar_229_2026_06_12_18_00)
                date_key = date_str.replace("-", "_")
                time_key = s["hora"].replace(":", "_")
                command = f"/agendar_{service_id}_{date_key}_{time_key}"
                lines.append(f"• ⏰ `{s['hora']}` 🎟️ `{s['cupos']}` cupos 👉 {command}")
            lines.append("")  # Espacio entre fechas

        lines.append("🔗 _Reserva en la Tienda de Diversión Colsubsidio_")
        message = "\n".join(lines)

        success = self.send_message(message)
        if success:
            self._sent_alerts[key] = time.time()
            return True

        return False

