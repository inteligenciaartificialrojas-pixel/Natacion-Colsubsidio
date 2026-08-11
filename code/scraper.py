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
        csrf_val = cookies.get("Csrf-Token") or cookies.get("csrf-token") or cookies.get("CSRF-TOKEN")
        
        if sistema_val:
            self.session.cookies.set("sistema", sistema_val, domain="www.diversioncolsubsidio.com")
            self.session.cookies.set("sistema", sistema_val, domain=".diversioncolsubsidio.com")
            self.session.cookies.set("sitio", sistema_val, domain="www.diversioncolsubsidio.com")
            self.session.cookies.set("sitio", sistema_val, domain=".diversioncolsubsidio.com")
        if csrf_val:
            self.session.cookies.set("Csrf-Token", csrf_val, domain="www.diversioncolsubsidio.com")
            self.session.cookies.set("Csrf-Token", csrf_val, domain=".diversioncolsubsidio.com")
            self.session.headers["Csrf-Token"] = csrf_val

    def _renew_session(self) -> dict[str, str]:
        """Intenta renovar la sesión mediante Playwright o extracción local de cookies,
        actualizando la sesión en memoria y guardando las nuevas cookies en el archivo .env.
        """
        logger.info("Iniciando renovación de sesión de Colsubsidio...")
        from get_cookies import extract_colsubsidio_cookies, update_env_file

        new_cookies = extract_colsubsidio_cookies()
        if not new_cookies or "sistema" not in new_cookies:
            raise SessionExpiredException("No se pudieron obtener nuevas cookies de sesión durante la renovación.")

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
                    self._renew_session()
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
                        "cupos": cupos,
                        "raw_horario": h.get("horario", {}),
                        "zonas": h.get("zonas", [])
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

    def book_slot(self, service_id: int, date_str: str, time_str: str, tiquetera_id: int) -> tuple[bool, str]:
        """
        Intenta reservar un slot de natación específico utilizando la tiquetera especificada.
        Retorna (True, mensaje_exito) o (False, mensaje_error).
        """
        # 1. Obtener la disponibilidad de la fecha para extraer el slot con su raw_horario y zonas
        slots = self.fetch_slots_for_date(service_id, date_str)
        target_slot = None
        for s in slots:
            if s["hora"] == time_str:
                target_slot = s
                break
        
        if not target_slot:
            return False, f"El horario {time_str} ya no está disponible en la fecha {date_str}."
        
        # 2. Seleccionar la primera zona/carril disponible
        selected_zone_id = None
        for z in target_slot.get("zonas", []):
            z_cupos = z.get("cupos", z.get("capacidad_disponible", 0))
            if z_cupos > 0:
                selected_zone_id = z.get("id")
                break
        
        if not selected_zone_id:
            return False, "No hay carriles (zonas) con cupo disponible para este horario."

        # Importaciones diferidas
        from config import COLSUBSIDIO_DOCUMENT_TYPE, COLSUBSIDIO_DOCUMENT_NUMBER

        persona = {
            "tipo_documento": COLSUBSIDIO_DOCUMENT_TYPE or "CC",
            "documento": COLSUBSIDIO_DOCUMENT_NUMBER,
            "datos": {
                "zona": 1
            }
        }

        materiales = [
            {
                "persona": persona,
                "informacion_compra_material": []
            }
        ]

        payload = {
            "servicio": {
                "id": service_id,
                "tipo": 2
            },
            "turnos_practica_libre": [
                {
                    "horario": {
                        "fecha": target_slot["raw_horario"].get("fecha"),
                        "hora_inicio": target_slot["raw_horario"].get("hora_inicio"),
                        "hora_fin": target_slot["raw_horario"].get("hora_fin")
                    },
                    "tiquetera": tiquetera_id,
                    "cantidad_usos": 1,
                    "numero_participantes": 1,
                    "persona": persona,
                    "materiales": materiales,
                    "zona": [
                        {
                            "id": selected_zone_id
                        }
                    ]
                }
            ]
        }

        url = f"https://www.diversioncolsubsidio.com/v1/centro_entrenamiento/{service_id}/practicalibre/reservar"

        def _make_request():
            logger.info("Realizando petición de reserva al servicio %s...", service_id)
            response = self.session.post(url, json=payload, timeout=20)
            self._check_unauthorized(response)
            return response

        try:
            response = self._execute_with_retry(_make_request)

            if response.status_code in [200, 201]:
                res_data = response.json()
                if "turnos_practica_libre" in res_data:
                    return True, "Reserva realizada con éxito en la plataforma."
                else:
                    return False, f"La respuesta de la plataforma no confirmó la reserva: {response.text}"
            else:
                try:
                    res_data = response.json()
                    err = res_data.get("mensaje") or res_data.get("error", {}).get("message") or response.text
                except Exception:
                    err = response.text
                return False, f"Error del servidor (HTTP {response.status_code}): {err}"
        except SessionExpiredException:
            raise
        except Exception as e:
            logger.error("Error al procesar la reserva: %s", e)
            return False, f"Fallo en la comunicación con Colsubsidio: {e}"

