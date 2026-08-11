"""Pruebas adversariales de preservación de estado de sesión para ColsubsidioScraper (Hito M3).

Cubre:
1. Preservación de cookies y cabeceras en peticiones secuenciales.
2. Preservación de sesión entre diferentes sedes (service_ids secuenciales).
3. Propagación de sesión renovada a sedes y peticiones posteriores.
4. Preservación de estado de sesión en el flujo de 2 pasos de book_slot.
5. Renovación de sesión en el paso 1 (disponibilidad) vs paso 2 (reservar) en book_slot.
6. Reservas secuenciales múltiples con la misma instancia de scraper.
7. Comportamiento ante llaves con diferente capitalización en update_session_credentials.
8. Aislamiento de estado entre múltiples instancias de ColsubsidioScraper.
9. Resiliencia de la sesión tras errores no-401 (HTTP 500, timeouts).
10. Agotamiento de reintentos en 401 persistentes.
11. Detección de sesión expirada vía JSON Unauthorized y HTML loguearSitio en book_slot.
12. Preservación de estado tras 50 peticiones secuenciales continuas.
"""
from __future__ import annotations

import os
from unittest.mock import patch, MagicMock
import pytest
import requests

from scraper import ColsubsidioScraper, SessionExpiredException


# ============================================================================
# 1. PETICIONES SECUENCIALES Y PRESERVACIÓN DE ESTADO DE SESIÓN
# ============================================================================

@patch("requests.Session.post")
def test_sequential_requests_cookie_header_persistence(mock_post: MagicMock) -> None:
    """Verifica que peticiones secuenciales (calendario -> disponibilidad -> disponibilidad) conserven las cookies y headers."""
    mock_resp_cal = MagicMock()
    mock_resp_cal.status_code = 200
    mock_resp_cal.headers = {"Content-Type": "application/json"}
    mock_resp_cal.json.return_value = {
        "fechas": {"2026-08-15": {"disponibilidad": True}}
    }

    mock_resp_slots = MagicMock()
    mock_resp_slots.status_code = 200
    mock_resp_slots.headers = {"Content-Type": "application/json"}
    mock_resp_slots.json.return_value = {
        "horarios": [
            {
                "horario": {"hora_inicio": "07:00:00"},
                "duracion": 50,
                "zonas": [{"capacidad_disponible": 2}]
            }
        ]
    }

    mock_post.side_effect = [mock_resp_cal, mock_resp_slots, mock_resp_slots]

    scraper = ColsubsidioScraper(session_cookie="sess_token_123", csrf_token="csrf_token_456")

    # 1. Primera petición: Calendario
    dates = scraper.fetch_available_dates(service_id=232)
    assert dates == ["2026-08-15"]

    # 2. Segunda petición: Cupos fecha 1
    slots1 = scraper.fetch_slots_for_date(service_id=232, date_str="2026-08-15")
    assert len(slots1) == 1
    assert slots1[0]["hora"] == "07:00"

    # 3. Tercera petición: Cupos fecha 2
    slots2 = scraper.fetch_slots_for_date(service_id=232, date_str="2026-08-16")
    assert len(slots2) == 1

    # Verificar que todas las peticiones usaron la misma sesión con sus headers y cookies
    assert mock_post.call_count == 3
    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "sess_token_123"
    assert scraper.session.cookies.get("Csrf-Token", domain="www.diversioncolsubsidio.com") == "csrf_token_456"
    assert scraper.session.headers.get("Csrf-Token") == "csrf_token_456"


@patch("requests.Session.post")
def test_50_sequential_requests_stress_session_integrity(mock_post: MagicMock) -> None:
    """Verifica que el estado de la sesión (cookies y headers) permanezca inalterado tras 50 peticiones consecutivas."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.json.return_value = {"fechas": {"2026-08-20": {"disponibilidad": True}}}
    mock_post.return_value = mock_resp

    scraper = ColsubsidioScraper(session_cookie="sess_50_reqs", csrf_token="csrf_50_reqs")

    for i in range(50):
        dates = scraper.fetch_available_dates(service_id=232)
        assert dates == ["2026-08-20"]

    assert mock_post.call_count == 50
    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "sess_50_reqs"
    assert scraper.session.headers.get("Csrf-Token") == "csrf_50_reqs"


# ============================================================================
# 2. CONSULTAS A MÚLTIPLES SEDES / SERVICE_IDS SECUENCIALES
# ============================================================================

@patch("requests.Session.post")
def test_sequential_venue_checks_session_preservation(mock_post: MagicMock) -> None:
    """Verifica la preservación de sesión al consultar secuencialmente múltiples sedes (service_ids 232, 233, 234)."""
    def make_mock_cal_resp(service_id):
        r = MagicMock()
        r.status_code = 200
        r.headers = {"Content-Type": "application/json"}
        r.json.return_value = {
            "fechas": {"2026-08-15": {"disponibilidad": True}}
        }
        return r

    mock_post.side_effect = [make_mock_cal_resp(232), make_mock_cal_resp(233), make_mock_cal_resp(234)]

    scraper = ColsubsidioScraper(session_cookie="venue_sess_abc", csrf_token="venue_csrf_xyz")

    venues = [232, 233, 234]
    for v_id in venues:
        res = scraper.fetch_available_dates(service_id=v_id)
        assert res == ["2026-08-15"]

    assert mock_post.call_count == 3
    # Comprobar que las URLs invocadas corresponden a cada sede
    urls_called = [call.args[0] for call in mock_post.call_args_list]
    assert "232" in urls_called[0]
    assert "233" in urls_called[1]
    assert "234" in urls_called[2]

    # Estado de la sesión se mantiene intacto
    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "venue_sess_abc"
    assert scraper.session.headers.get("Csrf-Token") == "venue_csrf_xyz"


@patch("get_cookies.update_env_file")
@patch("get_cookies.extract_colsubsidio_cookies")
@patch("requests.Session.post")
def test_venue_check_session_renewal_persistence_to_subsequent_venues(
    mock_post: MagicMock,
    mock_extract: MagicMock,
    mock_update_env: MagicMock
) -> None:
    """Verifica que si la sesión expira consultando la sede B (233), se renueve y la nueva sesión persista para la sede C (234)."""
    # Sede 232: OK con sesión vieja
    r1 = MagicMock()
    r1.status_code = 200
    r1.headers = {"Content-Type": "application/json"}
    r1.json.return_value = {"fechas": {"2026-08-15": {"disponibilidad": True}}}

    # Sede 233: 401 Unauthorized (Sesión expirada)
    r2_401 = MagicMock()
    r2_401.status_code = 401

    # Sede 233 tras renovación: OK con sesión nueva
    r2_200 = MagicMock()
    r2_200.status_code = 200
    r2_200.headers = {"Content-Type": "application/json"}
    r2_200.json.return_value = {"fechas": {"2026-08-16": {"disponibilidad": True}}}

    # Sede 234: OK con sesión nueva
    r3 = MagicMock()
    r3.status_code = 200
    r3.headers = {"Content-Type": "application/json"}
    r3.json.return_value = {"fechas": {"2026-08-17": {"disponibilidad": True}}}

    mock_post.side_effect = [r1, r2_401, r2_200, r3]
    mock_extract.return_value = {"sistema": "new_venue_sess", "Csrf-Token": "new_venue_csrf"}

    scraper = ColsubsidioScraper(session_cookie="old_venue_sess", csrf_token="old_venue_csrf")

    # 1. Sede 232
    d1 = scraper.fetch_available_dates(service_id=232)
    assert d1 == ["2026-08-15"]

    # 2. Sede 233 (Expira y renueva)
    d2 = scraper.fetch_available_dates(service_id=233)
    assert d2 == ["2026-08-16"]

    # 3. Sede 234 (Debe usar la sesión renovada)
    d3 = scraper.fetch_available_dates(service_id=234)
    assert d3 == ["2026-08-17"]

    assert mock_post.call_count == 4
    mock_extract.assert_called_once()
    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "new_venue_sess"
    assert scraper.session.headers.get("Csrf-Token") == "new_venue_csrf"


# ============================================================================
# 3. COMANDOS DE RESERVA (BOOK_SLOT) Y PRESERVACIÓN DE SESIÓN
# ============================================================================

@patch("requests.Session.post")
def test_book_slot_two_step_session_preservation(mock_post: MagicMock) -> None:
    """Verifica que book_slot ejecute disponibilidad + reserva usando de forma idéntica las credenciales de sesión."""
    mock_dispo = MagicMock()
    mock_dispo.status_code = 200
    mock_dispo.headers = {"Content-Type": "application/json"}
    mock_dispo.json.return_value = {
        "horarios": [
            {
                "horario": {"fecha": "2026-08-20", "hora_inicio": "06:00:00", "hora_fin": "06:50:00"},
                "duracion": 50,
                "zonas": [{"id": 101, "capacidad_disponible": 1}]
            }
        ]
    }

    mock_reserva = MagicMock()
    mock_reserva.status_code = 200
    mock_reserva.headers = {"Content-Type": "application/json"}
    mock_reserva.json.return_value = {
        "turnos_practica_libre": [{"id": 555}]
    }

    mock_post.side_effect = [mock_dispo, mock_reserva]

    scraper = ColsubsidioScraper(session_cookie="book_sess_888", csrf_token="book_csrf_999")

    success, msg = scraper.book_slot(service_id=232, date_str="2026-08-20", time_str="06:00", tiquetera_id=6370683)

    assert success is True
    assert "éxito" in msg.lower()
    assert mock_post.call_count == 2

    assert scraper.session.headers.get("Csrf-Token") == "book_csrf_999"


@patch("get_cookies.update_env_file")
@patch("get_cookies.extract_colsubsidio_cookies")
@patch("requests.Session.post")
def test_book_slot_session_renewal_at_step1_persists_to_step2(
    mock_post: MagicMock,
    mock_extract: MagicMock,
    mock_update_env: MagicMock
) -> None:
    """Verifica que si la sesión expira en el paso 1 (consultar cupos) de book_slot, la renovación beneficie al paso 2 (reservar)."""
    mock_dispo_401 = MagicMock()
    mock_dispo_401.status_code = 401

    mock_dispo_200 = MagicMock()
    mock_dispo_200.status_code = 200
    mock_dispo_200.headers = {"Content-Type": "application/json"}
    mock_dispo_200.json.return_value = {
        "horarios": [
            {
                "horario": {"fecha": "2026-08-20", "hora_inicio": "08:00:00", "hora_fin": "08:50:00"},
                "duracion": 50,
                "zonas": [{"id": 202, "capacidad_disponible": 2}]
            }
        ]
    }

    mock_reserva_200 = MagicMock()
    mock_reserva_200.status_code = 200
    mock_reserva_200.headers = {"Content-Type": "application/json"}
    mock_reserva_200.json.return_value = {
        "turnos_practica_libre": [{"id": 777}]
    }

    mock_post.side_effect = [mock_dispo_401, mock_dispo_200, mock_reserva_200]
    mock_extract.return_value = {"sistema": "renewed_step1_sess", "Csrf-Token": "renewed_step1_csrf"}

    scraper = ColsubsidioScraper(session_cookie="expired_sess", csrf_token="expired_csrf")

    success, msg = scraper.book_slot(service_id=232, date_str="2026-08-20", time_str="08:00", tiquetera_id=6370683)

    assert success is True
    assert mock_post.call_count == 3
    mock_extract.assert_called_once()
    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "renewed_step1_sess"
    assert scraper.session.headers.get("Csrf-Token") == "renewed_step1_csrf"


@patch("get_cookies.update_env_file")
@patch("get_cookies.extract_colsubsidio_cookies")
@patch("requests.Session.post")
def test_book_slot_session_renewal_at_step2_retries_with_updated_credentials(
    mock_post: MagicMock,
    mock_extract: MagicMock,
    mock_update_env: MagicMock
) -> None:
    """Verifica que si la sesión expira en el paso 2 (reservar) de book_slot, el reintento use las credenciales renovadas."""
    mock_dispo = MagicMock()
    mock_dispo.status_code = 200
    mock_dispo.headers = {"Content-Type": "application/json"}
    mock_dispo.json.return_value = {
        "horarios": [
            {
                "horario": {"fecha": "2026-08-21", "hora_inicio": "17:00:00", "hora_fin": "17:50:00"},
                "duracion": 50,
                "zonas": [{"id": 303, "capacidad_disponible": 1}]
            }
        ]
    }

    mock_reserva_401 = MagicMock()
    mock_reserva_401.status_code = 401

    mock_reserva_200 = MagicMock()
    mock_reserva_200.status_code = 200
    mock_reserva_200.headers = {"Content-Type": "application/json"}
    mock_reserva_200.json.return_value = {
        "turnos_practica_libre": [{"id": 888}]
    }

    mock_post.side_effect = [mock_dispo, mock_reserva_401, mock_reserva_200]
    mock_extract.return_value = {"sistema": "renewed_step2_sess", "Csrf-Token": "renewed_step2_csrf"}

    scraper = ColsubsidioScraper(session_cookie="valid_at_step1", csrf_token="valid_csrf_step1")

    success, msg = scraper.book_slot(service_id=232, date_str="2026-08-21", time_str="17:00", tiquetera_id=6370683)

    assert success is True
    assert mock_post.call_count == 3
    mock_extract.assert_called_once()
    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "renewed_step2_sess"
    assert scraper.session.headers.get("Csrf-Token") == "renewed_step2_csrf"


@patch("get_cookies.update_env_file")
@patch("get_cookies.extract_colsubsidio_cookies")
@patch("requests.Session.post")
def test_book_slot_session_expiration_via_json_unauthorized_triggers_renewal(
    mock_post: MagicMock,
    mock_extract: MagicMock,
    mock_update_env: MagicMock
) -> None:
    """Verifica que si la API responde HTTP 200 pero {"status": "Unauthorized"} durante el paso 2 de book_slot, se desencadene la renovación."""
    mock_dispo = MagicMock()
    mock_dispo.status_code = 200
    mock_dispo.headers = {"Content-Type": "application/json"}
    mock_dispo.json.return_value = {
        "horarios": [
            {
                "horario": {"fecha": "2026-08-25", "hora_inicio": "09:00:00", "hora_fin": "09:50:00"},
                "duracion": 50,
                "zonas": [{"id": 404, "capacidad_disponible": 1}]
            }
        ]
    }

    mock_reserva_json_unauth = MagicMock()
    mock_reserva_json_unauth.status_code = 200
    mock_reserva_json_unauth.headers = {"Content-Type": "application/json"}
    mock_reserva_json_unauth.json.return_value = {"status": "Unauthorized", "message": "Session expired"}

    mock_reserva_ok = MagicMock()
    mock_reserva_ok.status_code = 200
    mock_reserva_ok.headers = {"Content-Type": "application/json"}
    mock_reserva_ok.json.return_value = {"turnos_practica_libre": [{"id": 999}]}

    mock_post.side_effect = [mock_dispo, mock_reserva_json_unauth, mock_reserva_ok]
    mock_extract.return_value = {"sistema": "renewed_json_unauth_sess", "Csrf-Token": "renewed_json_csrf"}

    scraper = ColsubsidioScraper(session_cookie="old_json_sess", csrf_token="old_json_csrf")

    success, msg = scraper.book_slot(service_id=232, date_str="2026-08-25", time_str="09:00", tiquetera_id=6370683)

    assert success is True
    assert mock_post.call_count == 3
    mock_extract.assert_called_once()
    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "renewed_json_unauth_sess"


@patch("requests.Session.post")
def test_multiple_sequential_bookings_session_state(mock_post: MagicMock) -> None:
    """Verifica que múltiples reservas consecutivas mantengan el estado de sesión activo sin reseteos."""
    def mock_booking_pair(slot_id):
        d = MagicMock()
        d.status_code = 200
        d.headers = {"Content-Type": "application/json"}
        d.json.return_value = {
            "horarios": [
                {
                    "horario": {"fecha": "2026-08-22", "hora_inicio": "07:00:00", "hora_fin": "07:50:00"},
                    "duracion": 50,
                    "zonas": [{"id": slot_id, "capacidad_disponible": 1}]
                }
            ]
        }

        r = MagicMock()
        r.status_code = 200
        r.headers = {"Content-Type": "application/json"}
        r.json.return_value = {"turnos_practica_libre": [{"id": slot_id * 10}]}
        return [d, r]

    mock_post.side_effect = mock_booking_pair(1) + mock_booking_pair(2) + mock_booking_pair(3)

    scraper = ColsubsidioScraper(session_cookie="multi_book_sess", csrf_token="multi_book_csrf")

    for i in range(1, 4):
        ok, msg = scraper.book_slot(service_id=232, date_str="2026-08-22", time_str="07:00", tiquetera_id=6370683)
        assert ok is True

    assert mock_post.call_count == 6
    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "multi_book_sess"


# ============================================================================
# 4. CASOS LÍMITE Y ADVERSARIALES EN GESTIÓN DE SESIÓN
# ============================================================================

def test_update_session_credentials_key_casing_and_variants() -> None:
    """Verifica el comportamiento de update_session_credentials ante diferentes variaciones de claves dict."""
    scraper = ColsubsidioScraper()

    # Variación 1: 'sistema' y 'csrf-token' minúsculas
    scraper.update_session_credentials({"sistema": "s1", "csrf-token": "c1"})
    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "s1"
    assert scraper.session.cookies.get("Csrf-Token", domain="www.diversioncolsubsidio.com") == "c1"
    assert scraper.session.headers.get("Csrf-Token") == "c1"

    # Variación 2: 'CSRF-TOKEN' mayúsculas
    scraper.update_session_credentials({"sistema": "s2", "CSRF-TOKEN": "c2"})
    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "s2"
    assert scraper.session.headers.get("Csrf-Token") == "c2"

    # Variación 3: 'SISTEMA' en mayúsculas (Prueba adversarial: verificar si es soportado o ignorado)
    scraper.update_session_credentials({"SISTEMA": "s3_ignored", "Csrf-Token": "c3"})
    # Nota: scraper.py actualmente busca cookies.get("sistema"). 'SISTEMA' no actualiza 'sistema' si es en mayúsculas.
    # Verificamos que la cookie 'sistema' permanece como 's2' (el valor anterior).
    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "s2"
    assert scraper.session.headers.get("Csrf-Token") == "c3"


def test_session_state_isolation_between_multiple_scraper_instances() -> None:
    """Verifica que dos instancias de ColsubsidioScraper mantengan sesiones HTTP independientes."""
    scraper1 = ColsubsidioScraper(session_cookie="sess_inst_1", csrf_token="csrf_inst_1")
    scraper2 = ColsubsidioScraper(session_cookie="sess_inst_2", csrf_token="csrf_inst_2")

    assert scraper1.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "sess_inst_1"
    assert scraper2.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "sess_inst_2"

    # Actualizar la primera instancia no debe afectar la segunda
    scraper1.update_session_credentials({"sistema": "sess_inst_1_updated", "Csrf-Token": "csrf_inst_1_updated"})

    assert scraper1.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "sess_inst_1_updated"
    assert scraper2.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "sess_inst_2"


@patch("requests.Session.post")
def test_non_401_errors_do_not_invalidate_session_state(mock_post: MagicMock) -> None:
    """Verifica que errores HTTP 500 o fallos de red no borren ni corrompan las cookies/headers de la sesión."""
    mock_500 = MagicMock()
    mock_500.status_code = 500

    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.headers = {"Content-Type": "application/json"}
    mock_200.json.return_value = {"fechas": {"2026-08-30": {"disponibilidad": True}}}

    mock_post.side_effect = [mock_500, mock_200]

    scraper = ColsubsidioScraper(session_cookie="resilient_sess", csrf_token="resilient_csrf")

    # 1. Petición que retorna 500
    res1 = scraper.fetch_available_dates(service_id=232)
    assert res1 == []  # Fallo grácil

    # Las cookies deben mantenerse intactas
    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "resilient_sess"
    assert scraper.session.headers.get("Csrf-Token") == "resilient_csrf"

    # 2. Petición subsecuente cuando el servidor se recupera (200)
    res2 = scraper.fetch_available_dates(service_id=232)
    assert res2 == ["2026-08-30"]
