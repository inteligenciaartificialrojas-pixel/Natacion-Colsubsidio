"""Suite de Pruebas E2E Basada en Requerimientos (Tiers 1-4).

Cubre:
- Tier 1: Scraper de la API de disponibilidad y manejo de cookies/sesión.
- Tier 2: Motor de filtros de horarios estrictos y días festivos colombianos.
- Tier 3: Formato limpio de alertas en Telegram y de-duplicación de estado.
- Tier 4: Flujo de trabajo y orquestación E2E completa.
"""
from __future__ import annotations

import os
import sys
import json
import time
from datetime import datetime, date
from unittest.mock import patch, MagicMock
import pytest
import requests

from scraper import ColsubsidioScraper, SessionExpiredException
from notifier import TelegramNotifier
from main import (
    is_within_preferred_schedule,
    is_colombian_holiday,
    find_new_slots,
    load_cooldown_state,
    save_cooldown_state,
    load_last_slots,
    save_last_slots,
    check_venues,
    main,
)
import config


# ============================================================================
# TIER 1: AVAILABILITY API SCRAPER & COOKIE SESSION HANDLING
# ============================================================================

def test_tier1_scraper_init_and_headers() -> None:
    """Verifica que ColsubsidioScraper inicialice headers HTTP y cookies de sesión correctamente."""
    scraper = ColsubsidioScraper(session_cookie="test_sistema_val", csrf_token="test_csrf_val")
    
    # Headers base
    headers = scraper.session.headers
    assert headers.get("Accept") == "application/json"
    assert headers.get("Content-Type") == "application/json"
    assert "diversioncolsubsidio.com" in headers.get("Referer", "")
    assert headers.get("Csrf-Token") == "test_csrf_val"

    # Cookies de la sesión HTTP
    cookies = scraper.session.cookies.get_dict()
    assert cookies.get("sistema") == "test_sistema_val"
    assert cookies.get("Csrf-Token") == "test_csrf_val"


def test_tier1_update_session_credentials() -> None:
    """Verifica que update_session_credentials actualice las cookies e in-memory headers."""
    scraper = ColsubsidioScraper(session_cookie="old_cookie", csrf_token="old_csrf")
    
    new_credentials = {
        "sistema": "fresh_cookie_123",
        "Csrf-Token": "fresh_csrf_456"
    }
    scraper.update_session_credentials(new_credentials)

    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "fresh_cookie_123"
    assert scraper.session.cookies.get("sitio", domain="www.diversioncolsubsidio.com") == "fresh_cookie_123"
    assert scraper.session.cookies.get("Csrf-Token", domain="www.diversioncolsubsidio.com") == "fresh_csrf_456"
    assert scraper.session.headers.get("Csrf-Token") == "fresh_csrf_456"


@patch("requests.Session.post")
def test_tier1_fetch_available_dates_endpoint_payload(mock_post: MagicMock) -> None:
    """Verifica la consulta al endpoint de calendario con la estructura payload adecuada."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {
        "fechas": {
            "2026-08-15": {"fecha": "2026-08-15", "disponibilidad": True},
            "2026-08-16": {"fecha": "2026-08-16", "disponibilidad": False},
            "2026-08-17": {"fecha": "2026-08-17", "disponibilidad": True}
        }
    }
    mock_post.return_value = mock_response

    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")
    dates = scraper.fetch_available_dates(service_id=232)

    assert dates == ["2026-08-15", "2026-08-17"]
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "centro_entrenamiento/232/practicalibre/calendario" in args[0]
    payload = kwargs.get("json", {})
    assert "filtro_disponibilidad" in payload
    assert payload["filtro_disponibilidad"]["inicio_inmediato"] is False


@patch("requests.Session.post")
def test_tier1_fetch_slots_for_date_endpoint_payload(mock_post: MagicMock) -> None:
    """Verifica la consulta al endpoint de disponibilidad de fecha específica."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {
        "horarios": [
            {
                "horario": {"hora_inicio": "18:00:00"},
                "duracion": 50,
                "cupos": 3,
                "zonas": [{"capacidad_disponible": 3}]
            }
        ]
    }
    mock_post.return_value = mock_response

    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")
    slots = scraper.fetch_slots_for_date(service_id=428, date_str="2026-08-20")

    assert len(slots) == 1
    assert slots[0]["fecha"] == "2026-08-20"
    assert slots[0]["hora"] == "18:00"
    assert slots[0]["cupos"] == 3
    args, kwargs = mock_post.call_args
    assert "centro_entrenamiento/428/practicalibre/disponibilidad" in args[0]
    assert "filtrarSinCupo=0" in args[0]
    payload = kwargs.get("json", {})
    assert payload["filtro_disponibilidad"]["fecha_inicio"].startswith("2026-08-20T00:00:00")


@patch("requests.Session.post")
def test_tier1_slot_normalization_time_and_capacity(mock_post: MagicMock) -> None:
    """Verifica la normalización del formato de hora (HH:MM) y la suma de cupos por zona si cupos padre es None."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {
        "horarios": [
            {
                "horario": {"hora_inicio": "06:30:00"},
                "duracion": 50,
                "cupos": None,
                "zonas": [
                    {"capacidad_disponible": 2},
                    {"cupos": 3}
                ]
            }
        ]
    }
    mock_post.return_value = mock_response

    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")
    slots = scraper.fetch_slots_for_date(service_id=229, date_str="2026-08-21")

    assert len(slots) == 1
    assert slots[0]["hora"] == "06:30"
    assert slots[0]["cupos"] == 5


@patch("requests.Session.post")
def test_tier1_session_expired_http_401(mock_post: MagicMock) -> None:
    """Verifica la detección de sesión expirada mediante código de estado HTTP 401."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_post.return_value = mock_response

    scraper = ColsubsidioScraper(session_cookie="expired_sess", csrf_token="csrf")
    with pytest.raises(SessionExpiredException, match="401 Unauthorized"):
        scraper.fetch_available_dates(service_id=232)


@patch("requests.Session.post")
def test_tier1_session_expired_json_unauthorized(mock_post: MagicMock) -> None:
    """Verifica la detección de sesión expirada vía JSON status 'Unauthorized'."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {"status": "Unauthorized", "message": "Session inactive"}
    mock_post.return_value = mock_response

    scraper = ColsubsidioScraper(session_cookie="expired_sess", csrf_token="csrf")
    with pytest.raises(SessionExpiredException, match="Sesión no autorizada"):
        scraper.fetch_available_dates(service_id=232)


@patch("requests.Session.post")
def test_tier1_session_expired_html_redirect(mock_post: MagicMock) -> None:
    """Verifica la detección de sesión expirada mediante redirección HTML al login."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "text/html"}
    mock_response.text = "<html><body>Redireccionando a loguearSitio</body></html>"
    mock_post.return_value = mock_response

    scraper = ColsubsidioScraper(session_cookie="expired_sess", csrf_token="csrf")
    with pytest.raises(SessionExpiredException, match="redirección a login"):
        scraper.fetch_available_dates(service_id=232)


@patch("get_cookies.update_env_file")
@patch("get_cookies.extract_colsubsidio_cookies")
@patch("requests.Session.post")
def test_tier1_auto_retry_on_401_success(mock_post: MagicMock, mock_extract: MagicMock, mock_update: MagicMock) -> None:
    """Verifica que ante un 401 inicial el scraper renueve sesión y reintente exitosamente."""
    mock_resp_401 = MagicMock()
    mock_resp_401.status_code = 401

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.headers = {"Content-Type": "application/json"}
    mock_resp_200.json.return_value = {
        "fechas": {"2026-08-25": {"disponibilidad": True}}
    }

    mock_post.side_effect = [mock_resp_401, mock_resp_200]
    mock_extract.return_value = {"sistema": "new_cookie_999", "Csrf-Token": "new_csrf_999"}

    scraper = ColsubsidioScraper(session_cookie="old_cookie", csrf_token="old_csrf")
    dates = scraper.fetch_available_dates(service_id=232)

    assert dates == ["2026-08-25"]
    assert mock_post.call_count == 2
    mock_extract.assert_called_once()
    mock_update.assert_called_once_with({"sistema": "new_cookie_999", "Csrf-Token": "new_csrf_999"})


@patch("requests.Session.post")
def test_tier1_network_and_json_error_resilience(mock_post: MagicMock) -> None:
    """Verifica que errores HTTP 500, timeouts y JSONs inválidos sean manejados sin colapsar."""
    # 1. Error HTTP 500
    mock_500 = MagicMock()
    mock_500.status_code = 500
    mock_500.headers = {"Content-Type": "application/json"}
    mock_post.return_value = mock_500

    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")
    assert scraper.fetch_available_dates(service_id=232) == []
    assert scraper.fetch_slots_for_date(service_id=232, date_str="2026-08-25") == []

    # 2. Excepción de red / Timeout
    mock_post.side_effect = requests.RequestException("Timeout de red")
    assert scraper.fetch_available_dates(service_id=232) == []

    # 3. Parse error de JSON
    mock_bad_json = MagicMock()
    mock_bad_json.status_code = 200
    mock_bad_json.headers = {"Content-Type": "application/json"}
    mock_bad_json.json.side_effect = ValueError("JSON inválido")
    mock_post.side_effect = None
    mock_post.return_value = mock_bad_json
    assert scraper.fetch_available_dates(service_id=232) == []


# ============================================================================
# TIER 2: STRICT SCHEDULE FILTER ENGINE RULES & EDGE CASES
# ============================================================================

def test_tier2_weekday_evening_schedule() -> None:
    """Verifica horarios entre semana permitidos (Lunes a Viernes)."""
    # Lunes 2026-08-17 es festivo, probemos Lunes 2026-08-24 (Lunes normal)
    normal_monday = "2026-08-24"
    assert is_within_preferred_schedule(normal_monday, "18:00") is True
    assert is_within_preferred_schedule(normal_monday, "19:30") is True
    assert is_within_preferred_schedule(normal_monday, "20:00") is True


def test_tier2_weekday_outside_hours() -> None:
    """Verifica horarios fuera del rango en días entre semana normales."""
    normal_tuesday = "2026-08-25"
    assert is_within_preferred_schedule(normal_tuesday, "10:00") is False
    assert is_within_preferred_schedule(normal_tuesday, "14:00") is False
    assert is_within_preferred_schedule(normal_tuesday, "15:30") is False
    assert is_within_preferred_schedule(normal_tuesday, "22:00") is True


def test_tier2_weekend_24h_coverage() -> None:
    """Verifica que fines de semana (Sábados y Domingos) permitan cualquier hora."""
    saturday = "2026-08-22"
    sunday = "2026-08-23"

    for dt_str in [saturday, sunday]:
        assert is_within_preferred_schedule(dt_str, "06:00") is True
        assert is_within_preferred_schedule(dt_str, "12:00") is True
        assert is_within_preferred_schedule(dt_str, "16:00") is True
        assert is_within_preferred_schedule(dt_str, "21:00") is True


def test_tier2_colombian_fixed_holidays_24h_coverage() -> None:
    """Verifica que los festivos fijos colombianos permitan cualquier hora."""
    new_year = "2026-01-01"
    labor_day = "2026-05-01"
    independence = "2026-07-20"
    boyaca = "2026-08-07"
    christmas = "2026-12-25"

    for holiday_str in [new_year, labor_day, independence, boyaca, christmas]:
        dt = datetime.strptime(holiday_str, "%Y-%m-%d").date()
        assert is_colombian_holiday(dt) is True
        assert is_within_preferred_schedule(holiday_str, "08:00") is True
        assert is_within_preferred_schedule(holiday_str, "14:00") is True
        assert is_within_preferred_schedule(holiday_str, "21:00") is True


def test_tier2_colombian_emiliani_and_easter_holidays() -> None:
    """Verifica que festivos por Ley Emiliani y de Pascua sean calculados dinámicamente."""
    # En 2026:
    # Jueves Santo: 2026-04-02
    # Viernes Santo: 2026-04-03
    # Corpus Christi (trasladado a lunes): 2026-06-08
    easter_thursday = date(2026, 4, 2)
    easter_friday = date(2026, 4, 3)
    corpus_christi_monday = date(2026, 6, 8)

    assert is_colombian_holiday(easter_thursday) is True
    assert is_colombian_holiday(easter_friday) is True
    assert is_colombian_holiday(corpus_christi_monday) is True

    assert is_within_preferred_schedule("2026-04-02", "11:00") is True
    assert is_within_preferred_schedule("2026-06-08", "07:00") is True


def test_tier2_boundary_time_string_parsing() -> None:
    """Verifica robustez ante entradas de hora no estándar o malformadas."""
    normal_wednesday = "2026-08-26"
    
    # Manejo de error cuando la cadena no puede parsearse
    assert is_within_preferred_schedule(normal_wednesday, "invalid_time") is False
    assert is_within_preferred_schedule("invalid-date", "18:00") is False


def test_tier2_spec_schedule_rules_audit() -> None:
    """Auditoría de especificación de requerimientos (R2):
    Documenta la ventana preferida (<07:00 ó >=17:00) vs la ventana configurada actual.
    """
    # Lunes regular
    monday = "2026-08-24"
    # 18:00 coincide tanto con R2 (>=17:00) como con la implementación actual (18-20)
    assert is_within_preferred_schedule(monday, "18:00") is True
    # 13:00 está en ventana laboral excluida en ambos
    assert is_within_preferred_schedule(monday, "13:00") is False


# ============================================================================
# TIER 3: TELEGRAM NOTIFICATION FORMATTING & SLOT STATE DEDUPLICATION
# ============================================================================

def test_tier3_notifier_init_and_credentials() -> None:
    """Verifica la inicialización del notificador con token/chat_id y manejo sin credenciales."""
    notifier = TelegramNotifier(token="tok_123", chat_id="chat_456")
    assert notifier.token == "tok_123"
    assert notifier.chat_id == "chat_456"

    notifier_empty = TelegramNotifier(token=None, chat_id=None)
    assert notifier_empty.send_message("Test message") is False


@patch("requests.post")
def test_tier3_clean_message_formatting(mock_post: MagicMock) -> None:
    """Verifica que notify_venue_slots genere un mensaje en Markdown estructurado y limpio."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    notifier = TelegramNotifier(token="bot_token", chat_id="chat_id")
    slots = [
        {"fecha": "2026-08-24", "hora": "18:00", "cupos": 4},
        {"fecha": "2026-08-24", "hora": "19:00", "cupos": 2}
    ]

    result = notifier.notify_venue_slots("EL CUBO", slots)

    assert result is True
    mock_post.assert_called_once()
    payload = mock_post.call_args[1]["json"]
    text = payload["text"]
    assert "🏊 *¡Cupos Libres de Natación!*" in text
    assert "📍 *Sede:* EL CUBO" in text
    assert "📅 *Lunes 2026-08-24:*" in text
    assert "• ⏰ `18:00` — 🎟️ `4` cupos" in text
    assert "• ⏰ `19:00` — 🎟️ `2` cupos" in text


@patch("requests.post")
def test_tier3_slot_state_deduplication(mock_post: MagicMock) -> None:
    """Verifica la omisión de mensajes cuando los cupos de una sede son idénticos a los notificados."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    notifier = TelegramNotifier(token="bot_token", chat_id="chat_id", cache_duration_seconds=3600)
    slots = [{"fecha": "2026-08-24", "hora": "18:00", "cupos": 3}]

    # Primer llamado: envía mensaje
    assert notifier.notify_venue_slots("EL CUBO", slots) is True
    assert mock_post.call_count == 1

    # Segundo llamado idéntico: omitido por de-duplicación
    assert notifier.notify_venue_slots("EL CUBO", slots) is False
    assert mock_post.call_count == 1


@patch("requests.post")
def test_tier3_slot_state_delta_detection(mock_post: MagicMock) -> None:
    """Verifica que al detectar cambios en el número de cupos o un nuevo slot se envíe una nueva alerta."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    notifier = TelegramNotifier(token="bot_token", chat_id="chat_id", cache_duration_seconds=3600)
    
    slots_v1 = [{"fecha": "2026-08-24", "hora": "18:00", "cupos": 2}]
    assert notifier.notify_venue_slots("EL CUBO", slots_v1) is True
    assert mock_post.call_count == 1

    # Cambio en la cantidad de cupos
    slots_v2 = [{"fecha": "2026-08-24", "hora": "18:00", "cupos": 4}]
    assert notifier.notify_venue_slots("EL CUBO", slots_v2) is True
    assert mock_post.call_count == 2


@patch("requests.post")
def test_tier3_force_send_override(mock_post: MagicMock) -> None:
    """Verifica que force=True fuerce el envío aunque la clave esté duplicada en la caché."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    notifier = TelegramNotifier(token="bot_token", chat_id="chat_id", cache_duration_seconds=3600)
    slots = [{"fecha": "2026-08-24", "hora": "18:00", "cupos": 2}]

    assert notifier.notify_venue_slots("EL CUBO", slots) is True
    assert mock_post.call_count == 1

    # Forzar envío programado
    assert notifier.notify_venue_slots("EL CUBO", slots, force=True) is True
    assert mock_post.call_count == 2


@patch("requests.post")
@patch("time.time")
def test_tier3_cache_pruning_expiration(mock_time: MagicMock, mock_post: MagicMock) -> None:
    """Verifica que al expirar el tiempo de caché las alertas puedan enviarse nuevamente."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    mock_time.return_value = 1000.0
    notifier = TelegramNotifier(token="bot_token", chat_id="chat_id", cache_duration_seconds=60)
    slots = [{"fecha": "2026-08-24", "hora": "18:00", "cupos": 2}]

    assert notifier.notify_venue_slots("EL CUBO", slots) is True
    assert mock_post.call_count == 1

    # 30 segundos después: dentro de caché -> omitido
    mock_time.return_value = 1030.0
    assert notifier.notify_venue_slots("EL CUBO", slots) is False

    # 65 segundos después: expirado -> nuevo envío
    mock_time.return_value = 1065.0
    assert notifier.notify_venue_slots("EL CUBO", slots) is True
    assert mock_post.call_count == 2


def test_tier3_cooldown_state_and_last_slots_persistence(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica la lectura y escritura de archivos de estado (.cooldown_state y .last_slots.json)."""
    state_file = tmp_path / ".cooldown_state"
    slots_file = tmp_path / ".last_slots.json"

    monkeypatch.setattr("main.STATE_FILE", str(state_file))
    monkeypatch.setattr("main.LAST_SLOTS_FILE", str(slots_file))

    # Guardar y cargar cooldown state
    sample_state = {"last_expiry_alert_time": 1234567.8, "last_report_sent": "2026-08-24-18", "last_processed_update_id": 42}
    save_cooldown_state(sample_state)
    loaded_state = load_cooldown_state()
    assert loaded_state == sample_state

    # Guardar y cargar last slots
    sample_slots = {"EL CUBO": [{"fecha": "2026-08-24", "hora": "18:00", "cupos": 5}]}
    save_last_slots(sample_slots)
    loaded_slots = load_last_slots()
    assert loaded_slots == sample_slots


# ============================================================================
# TIER 4: END-TO-END EXECUTION WORKFLOW TEST CASES
# ============================================================================

@patch("main.save_last_slots")
@patch("main.load_last_slots")
def test_tier4_full_check_venues_workflow(mock_load: MagicMock, mock_save: MagicMock) -> None:
    """Verifica el flujo E2E de check_venues: consulta fechas, filtra cupos, notifica y guarda estado."""
    mock_load.return_value = {}

    mock_scraper = MagicMock(spec=ColsubsidioScraper)
    mock_notifier = MagicMock(spec=TelegramNotifier)

    # Scraper responde con fechas y slots
    mock_scraper.fetch_available_dates.return_value = ["2026-08-24"]
    mock_scraper.fetch_slots_for_date.return_value = [
        {"fecha": "2026-08-24", "hora": "18:00", "cupos": 3},  # Válido (Lunes 18:00)
        {"fecha": "2026-08-24", "hora": "12:00", "cupos": 1}   # Fuera de horario
    ]
    mock_notifier.notify_venue_slots.return_value = True

    check_venues(mock_scraper, mock_notifier, force_send=False)

    # Debe haber consultado disponibilidad para las 3 sedes
    assert mock_scraper.fetch_available_dates.call_count == 3
    # Debe haber filtrado dejando únicamente el slot de las 18:00
    expected_matching = [{"fecha": "2026-08-24", "hora": "18:00", "cupos": 3}]
    mock_notifier.notify_venue_slots.assert_any_call("EL CUBO", expected_matching, force=False)
    mock_save.assert_called_once()


def test_tier4_find_new_slots_orchestration() -> None:
    """Verifica la función find_new_slots que calcula el delta entre escaneos consecutivos."""
    last_slots = [
        {"fecha": "2026-08-24", "hora": "18:00", "cupos": 2},
        {"fecha": "2026-08-24", "hora": "19:00", "cupos": 1}
    ]

    # Sin cambios -> delta vacío
    curr_same = [
        {"fecha": "2026-08-24", "hora": "18:00", "cupos": 2},
        {"fecha": "2026-08-24", "hora": "19:00", "cupos": 1}
    ]
    assert find_new_slots(curr_same, last_slots) == []

    # Nuevo slot o incremento de cupos -> retorna solo el slot modificado
    curr_diff = [
        {"fecha": "2026-08-24", "hora": "18:00", "cupos": 5},  # Incrementó de 2 a 5
        {"fecha": "2026-08-24", "hora": "19:00", "cupos": 1},
        {"fecha": "2026-08-24", "hora": "20:00", "cupos": 1}   # Nuevo horario
    ]
    deltas = find_new_slots(curr_diff, last_slots)
    assert len(deltas) == 2
    assert deltas[0]["hora"] == "18:00" and deltas[0]["cupos"] == 5
    assert deltas[1]["hora"] == "20:00"


@patch("main.check_venues")
@patch("main.TelegramNotifier")
@patch("main.ColsubsidioScraper")
def test_tier4_main_once_mode_execution(
    mock_scraper_cls: MagicMock,
    mock_notifier_cls: MagicMock,
    mock_check: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pytest.TempPathFactory
) -> None:
    """Verifica la ejecución del bucle principal main() con la bandera --once."""
    state_file = tmp_path / ".cooldown_state"
    monkeypatch.setattr("main.STATE_FILE", str(state_file))
    monkeypatch.setattr("sys.argv", ["main.py", "--once"])

    notifier_inst = mock_notifier_cls.return_value
    notifier_inst.get_incoming_commands.return_value = []

    main()

    mock_check.assert_called_once()
    assert os.path.exists(state_file)


@patch("main.save_cooldown_state")
@patch("main.load_cooldown_state")
@patch("main.check_venues")
@patch("main.TelegramNotifier")
@patch("main.ColsubsidioScraper")
def test_tier4_session_expiration_workflow_in_main(
    mock_scraper_cls: MagicMock,
    mock_notifier_cls: MagicMock,
    mock_check: MagicMock,
    mock_load_state: MagicMock,
    mock_save_state: MagicMock,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica el manejo de SessionExpiredException en main() --once enviando alerta a Telegram."""
    monkeypatch.setattr("sys.argv", ["main.py", "--once"])
    mock_load_state.return_value = {"last_expiry_alert_time": 0.0}

    notifier_inst = mock_notifier_cls.return_value
    notifier_inst.get_incoming_commands.return_value = []
    notifier_inst.send_message.return_value = True

    mock_check.side_effect = SessionExpiredException("Cookie expirada")

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    notifier_inst.send_message.assert_called_once()
    assert "sesión de Colsubsidio" in notifier_inst.send_message.call_args[0][0]
    mock_save_state.assert_called_once()


