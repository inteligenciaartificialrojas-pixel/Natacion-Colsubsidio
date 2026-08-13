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

        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Referer": "https://www.diversioncolsubsidio.com/deportes-practica-libre-natacion"
        })

        if cookie_val or csrf_val:
            cookies_dict = {}
            if cookie_val:
                cookies_dict["sistema"] = cookie_val
            if csrf_val:
                cookies_dict["Csrf-Token"] = csrf_val
            self.update_session_credentials(cookies_dict)

    def update_session_credentials(self, cookies: dict[str, str]) -> None:
        """Actualiza en memoria las cookies (sistema, sitio, Csrf-Token) y los headers (Csrf-Token)."""
        sistema_val = cookies.get("sistema")
        csrf_val = (
            cookies.get("Csrf-Token")
            or cookies.get("csrf-token")
            or cookies.get("CSRF-TOKEN")
        )

        if sistema_val:
            self.session.cookies.set("sistema", sistema_val, domain="www.diversioncolsubsidio.com", path="/")
            self.session.cookies.set("sitio", sistema_val, domain="www.diversioncolsubsidio.com", path="/")
        if csrf_val:
            self.session.cookies.set("Csrf-Token", csrf_val, domain="www.diversioncolsubsidio.com", path="/")
            self.session.headers["Csrf-Token"] = csrf_val

    def _renew_session(self, reason: str = "") -> dict[str, str]:
        """Intenta renovar la sesión mediante Playwright o extracción local de cookies,
        actualizando la sesión en memoria y guardando las nuevas cookies en el archivo .env.
        """
        logger.info("Iniciando renovación de sesión de Colsubsidio...")
        from get_cookies import extract_colsubsidio_cookies, update_env_file

        try:
            new_cookies = extract_colsubsidio_cookies()
        except requests.RequestException:
            raise
        except Exception as exc:
            logger.error("Error inesperado durante la extracción de cookies: %s", exc)
            msg = f"Falla al extraer nuevas cookies: {exc}"
            if reason:
                msg += f" (causa original: {reason})"
            raise SessionExpiredException(msg) from exc

        if not new_cookies or "sistema" not in new_cookies:
            msg = "No se pudieron obtener nuevas cookies de sesión durante la renovación."
            if reason:
                msg += f" (causa original: {reason})"
            raise SessionExpiredException(msg)

        self.update_session_credentials(new_cookies)
        update_env_file(new_cookies)
        logger.info("Sesión renovada con éxito. Cookies e in-memory headers actualizados.")
        return new_cookies

    def _execute_with_retry(self, func, max_retries: int = 1):
        """Ejecuta una función que realiza una petición HTTP a la API.
        Si se detecta SessionExpiredException, renueva la sesión y reintenta hasta max_retries veces.
        """
        attempts = 0
        while True:
            try:
                return func()
            except SessionExpiredException as exc:
                if attempts < max_retries:
                    attempts += 1
                    logger.warning("Sesión expirada detectada (intento %d/%d). Renovando sesión...", attempts, max_retries)
                    self._renew_session(reason=str(exc))
                else:
                    logger.error("La sesión expiró y se superó el límite de reintentos (%d).", max_retries)
                    raise

    def _check_unauthorized(self, response: requests.Response) -> None:
        """Verifica si la respuesta indica que la sesión no está autorizada."""
        # 1. Verificar si el código HTTP es 401
        if response.status_code == 401:
            raise SessionExpiredException("La API retornó HTTP 401 Unauthorized.")
        
        # 2. Verificar si retornó 200 pero es una respuesta JSON con error de no autorizado
        try:
            if "application/json" in response.headers.get("Content-Type", ""):
                data = response.json()
                if isinstance(data, dict):
                    status_val = str(data.get("status", "")).lower()
                    code_val = str(data.get("code", "")).lower()
                    error_val = str(data.get("error", "")).lower()
                    msg_val = str(data.get("message", "")).lower()

                    if (status_val in ["unauthorized", "401"] or
                        code_val in ["unauthorized", "401"] or
                        error_val in ["unauthorized", "401"] or
                        "unauthorized" in msg_val or "session expired" in msg_val):
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

        def _make_request():
            logger.info("Consultando calendario para servicio ID %s...", service_id)
            response = self.session.post(url, json=payload, timeout=15)
            self._check_unauthorized(response)
            return response

        try:
            response = self._execute_with_retry(_make_request)

            if response.status_code != 200:
                logger.warning("Error HTTP al obtener calendario: %s", response.status_code)
                return []

            data = response.json()
            if not isinstance(data, dict):
                logger.warning("Respuesta inesperada (no es dict) en calendario: %s", type(data))
                return []

            fechas_dict = data.get("fechas")
            if not isinstance(fechas_dict, dict):
                logger.warning("'fechas' no es dict o es None en calendario: %s", type(fechas_dict))
                return []

            available_dates = []
            for fecha_str, info in fechas_dict.items():
                if isinstance(info, dict) and info.get("disponibilidad") is True:
                    available_dates.append(fecha_str)

            logger.info("Fechas disponibles encontradas: %s", available_dates)
            return sorted(available_dates)

        except SessionExpiredException:
            raise
        except (requests.RequestException, ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error al procesar respuesta del calendario: %s", e)
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

        def _make_request():
            logger.info("Consultando horarios para fecha %s en servicio %s...", date_str, service_id)
            response = self.session.post(url, json=payload, timeout=15)
            self._check_unauthorized(response)
            return response

        try:
            response = self._execute_with_retry(_make_request)

            if response.status_code != 200:
                logger.warning("Error HTTP al obtener horarios para %s: %s", date_str, response.status_code)
                return []

            data = response.json()
            if not isinstance(data, dict):
                logger.warning("Respuesta inesperada (no es dict) en horarios para %s: %s", date_str, type(data))
                return []

            horarios = data.get("horarios")
            if not isinstance(horarios, list):
                logger.warning("'horarios' no es lista o es None para %s: %s", date_str, type(horarios))
                return []

            slots = []
            for h in horarios:
                if not isinstance(h, dict):
                    continue

                horario_obj = h.get("horario")
                if not isinstance(horario_obj, dict):
                    continue

                hora_inicio = horario_obj.get("hora_inicio")
                if not isinstance(hora_inicio, str) or not hora_inicio:
                    continue

                # Normalizar formato de hora (HH:MM:SS -> HH:MM)
                parts = hora_inicio.split(":")
                hora_formatted = f"{parts[0]}:{parts[1]}" if len(parts) >= 2 else hora_inicio

                # Obtener cupos directamente del objeto padre o calcularlos sumando zonas
                cupos = h.get("cupos")
                if cupos is None:
                    zonas = h.get("zonas")
                    if isinstance(zonas, list):
                        cupos = 0
                        for z in zonas:
                            if isinstance(z, dict):
                                cap = z.get("cupos") if z.get("cupos") is not None else z.get("capacidad_disponible", 0)
                                try:
                                    cupos += int(cap)
                                except (ValueError, TypeError):
                                    pass
                    else:
                        cupos = 0

                try:
                    cupos_int = int(cupos) if cupos is not None else 0
                except (ValueError, TypeError):
                    cupos_int = 0

                if cupos_int > 0:
                    slots.append({
                        "fecha": date_str,
                        "hora": hora_formatted,
                        "cupos": cupos_int,
                        "raw_horario": horario_obj,
                        "zonas": h.get("zonas") if isinstance(h.get("zonas"), list) else []
                    })

            return slots

        except SessionExpiredException:
            raise
        except (requests.RequestException, ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error al procesar respuesta de horarios para %s: %s", date_str, e)
            return []


