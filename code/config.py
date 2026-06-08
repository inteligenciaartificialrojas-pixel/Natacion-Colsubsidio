"""Configuración y constantes para el Revisor de Natación Colsubsidio."""
from __future__ import annotations
import os

# Cargar archivo .env local si existe (evitando dependencias externas)
_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#"):
                continue
            _parts = _line.split("=", 1)
            if len(_parts) == 2:
                _key = _parts[0].strip()
                _val = _parts[1].strip().strip('"').strip("'")
                os.environ[_key] = _val

# Credenciales de Telegram (cargadas desde variables de entorno o .env)
TELEGRAM_TOKEN: str | None = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID: str | None = os.environ.get("TELEGRAM_CHAT_ID")

# Credenciales y Sesión de Colsubsidio
COLSUBSIDIO_SISTEMA_COOKIE: str | None = os.environ.get("COLSUBSIDIO_SISTEMA_COOKIE")
COLSUBSIDIO_CSRF_TOKEN: str | None = os.environ.get("COLSUBSIDIO_CSRF_TOKEN")
COLSUBSIDIO_DOCUMENT_TYPE: str = os.environ.get("COLSUBSIDIO_DOCUMENT_TYPE", "CC")
COLSUBSIDIO_DOCUMENT_NUMBER: str = os.environ.get("COLSUBSIDIO_DOCUMENT_NUMBER", "1002559691")

# ID de la tiquetera/plan para reservas automatizadas/interactivas
_tiq_val = os.environ.get("COLSUBSIDIO_TIQUETERA_ID") or "6370683"
COLSUBSIDIO_TIQUETERA_ID: int | None = int(_tiq_val) if _tiq_val.isdigit() else None

# Configuración de búsqueda
# Sedes de interés normalizadas en mayúsculas
PREFERRED_VENUES: list[str] = [
    "EL CUBO",
    "PLAZA DE LAS AMERICAS",
    "CLUB LA COLINA"
]

# Mapeo de Sede -> ID de Servicio (natación práctica libre) en la API de Colsubsidio
VENUE_SERVICE_IDS: dict[str, int] = {
    "EL CUBO": 232,
    "PLAZA DE LAS AMERICAS": 428,
    "CLUB LA COLINA": 229
}

# Reglas de horario para días entre semana (L-V)
WEEKDAY_START_HOUR: int = 18  # 6:00 PM
WEEKDAY_END_HOUR: int = 20    # 8:00 PM

# Intervalo por defecto de escaneo (en segundos)
DEFAULT_CHECK_INTERVAL_SECONDS: int = 300  # 5 minutos

# Duración de la caché de de-duplicación de alertas (en segundos)
ALERT_CACHE_DURATION_SECONDS: int = 3600  # 1 hora

