"""Módulo encargado de interactuar con la API de Colsubsidio para extraer cupos."""
from __future__ import annotations
import logging
import os
import requests
from datetime import datetime, timedelta
from config import COLSUBSIDIO_SISTEMA_COOKIE, COLSUBSIDIO_CSRF_TOKEN

logger = logging.getLogger(__name__)

class SessionExpiredException(Exception):
    """Excepción lanzada cuando la sesión de Colsubsidio (cookie 'sistema') expira."""
    pass

class ColsubsidioScraper:
    """Clase para consultar disponibilidad en la Tienda de Diversión Colsubsidio."""

    def __init__(self, session_cookie: str | None = None, csrf_token: str | None = None) -> None:
        """Inicializa la sesión HTTP con las cookies necesarias."""
        self.session = requests.Session()
        
        # Cargar cookies pasadas o leídas de la configuración
        cookie_val = session_cookie or COLSUBSIDIO_SISTEMA_COOKIE
        csrf_val = csrf_token or COLSUBSIDIO_CSRF_TOKEN

        if cookie_val:
            self.session.cookies.set("sistema", cookie_val, domain="www.diversioncolsubsidio.com")
            self.session.cookies.set("sistema", cookie_val, domain=".diversioncolsubsidio.com")
            self.session.cookies.set("sitio", cookie_val, domain="www.diversioncolsubsidio.com")
            self.session.cookies.set("sitio", cookie_val, domain=".diversioncolsubsidio.com")
        if csrf_val:
            self.session.cookies.set("Csrf-Token", csrf_val, domain="www.diversioncolsubsidio.com")
            self.session.cookies.set("Csrf-Token", csrf_val, domain=".diversioncolsubsidio.com")

        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Referer": "https://www.diversioncolsubsidio.com/deportes-practica-libre-natacion"
        })

    def _check_unauthorized(self, response: requests.Response) -> None:
        """Verifica si la respuesta indica que la sesión no está autorizada."""
        # 1. Verificar si el código HTTP es 401
        if response.status_code == 401:
            raise SessionExpiredException("La API retornó HTTP 401 Unauthorized.")
        
        # 2. Verificar si retornó 200 pero es una respuesta JSON con error de no autorizado
        try:
            if "application/json" in response.headers.get("Content-Type", ""):
                data = response.json()
                if isinstance(data, dict) and data.get("status") == "Unauthorized":
                    raise SessionExpiredException("Sesión no autorizada en el JSON de respuesta.")
        except (ValueError, TypeError):
            pass

        # 3. Verificar si retornó 200 pero es una redirección HTML a la página de login
        if "application/json" not in response.headers.get("Content-Type", ""):
            if "loguearSitio" in response.text or "error-no-encontrado" in response.text:
                raise SessionExpiredException("La sesión expiró (redirección a login o página no encontrada).")

    def fetch_available_dates(self, service_id: int) -> list[str]:
        """
        Consulta las fechas disponibles para el servicio especificado.
        Retorna una lista de cadenas de fechas ['YYYY-MM-DD', ...].
        """
        url = f"https://www.diversioncolsubsidio.com/v1/centro_entrenamiento/{service_id}/practicalibre/calendario"
        
        today_str = datetime.today().strftime('%Y-%m-%d')
        future_str = (datetime.today() + timedelta(days=14)).strftime('%Y-%m-%d')

        payload = {
            "filtro_disponibilidad": {
                "fecha_inicio": today_str,
                "fecha_fin": future_str,
                "inicio_inmediato": False
            }
        }

        try:
            logger.info("Consultando calendario para servicio ID %s...", service_id)
            response = self.session.post(url, json=payload, timeout=15)
            self._check_unauthorized(response)

            if response.status_code != 200:
                logger.warning("Error HTTP al obtener calendario: %s", response.status_code)
                return []

            data = response.json()
            fechas_dict = data.get("fechas", {})
            available_dates = [
                fecha_str for fecha_str, info in fechas_dict.items()
                if info.get("disponibilidad") is True
            ]
            logger.info("Fechas disponibles encontradas: %s", available_dates)
            return sorted(available_dates)

        except SessionExpiredException:
            raise
        except requests.RequestException as e:
            logger.error("Error de conexión al obtener calendario de Colsubsidio: %s", e)
            return []
        except ValueError as e:
            logger.error("Error al parsear el JSON del calendario: %s", e)
            return []

    def fetch_slots_for_date(self, service_id: int, date_str: str) -> list[dict]:
        """
        Consulta los horarios y cupos disponibles para una fecha específica.
        Retorna una lista de diccionarios [{'fecha': 'YYYY-MM-DD', 'hora': 'HH:MM', 'cupos': X}, ...].
        """
        url = f"https://www.diversioncolsubsidio.com/v1/centro_entrenamiento/{service_id}/practicalibre/disponibilidad?filtrarSinCupo=0"

        # Importaciones diferidas para evitar acoplamiento circular
        from config import COLSUBSIDIO_DOCUMENT_TYPE, COLSUBSIDIO_DOCUMENT_NUMBER

        # Formato ISO local con offset de Colombia (-05:00) para asegurar consistencia
        fecha_ini = f"{date_str}T00:00:00-05:00"
        fecha_fin = f"{date_str}T23:59:59-05:00"

        persona_data = []
        if COLSUBSIDIO_DOCUMENT_NUMBER:
            persona_data.append({
                "tipo_documento": COLSUBSIDIO_DOCUMENT_TYPE or "CC",
                "documento": COLSUBSIDIO_DOCUMENT_NUMBER,
                "datos": {}
            })

        payload = {
            "filtro_disponibilidad": {
                "fecha_inicio": fecha_ini,
                "fecha_fin": fecha_fin,
                "inicio_inmediato": False,
                "categorias_precios": ["A", "B", "C", "D", "INVITADO"]
            },
            "turno_practica_libre": {
                "cantidad_usos": 1,
                "numero_participantes": 1,
                "persona": persona_data
            }
        }

        try:
            logger.info("Consultando horarios para fecha %s en servicio %s...", date_str, service_id)
            response = self.session.post(url, json=payload, timeout=15)
            self._check_unauthorized(response)

            if response.status_code != 200:
                logger.warning("Error HTTP al obtener horarios para %s: %s", date_str, response.status_code)
                return []

            data = response.json()
            horarios = data.get("horarios", [])
            slots = []

            for h in horarios:
                hora_inicio = h.get("horario", {}).get("hora_inicio")
                if not hora_inicio:
                    continue
                
                # Normalizar formato de hora (HH:MM:SS -> HH:MM)
                parts = hora_inicio.split(":")
                hora_formatted = f"{parts[0]}:{parts[1]}" if len(parts) >= 2 else hora_inicio

                # Obtener cupos directamente del objeto padre o calcularlos sumando zonas
                cupos = h.get("cupos")
                if cupos is None:
                    cupos = sum(z.get("cupos", z.get("capacidad_disponible", 0)) for z in h.get("zonas", []))

                if cupos > 0:
                    slots.append({
                        "fecha": date_str,
                        "hora": hora_formatted,
                        "cupos": cupos
                    })

            return slots

        except SessionExpiredException:
            raise
        except requests.RequestException as e:
            logger.error("Error de conexión al obtener horarios para %s: %s", date_str, e)
            return []
        except ValueError as e:
            logger.error("Error al parsear el JSON de horarios para %s: %s", date_str, e)
            return []
