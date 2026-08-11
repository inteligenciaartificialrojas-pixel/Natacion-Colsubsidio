"""Pruebas unitarias para el módulo scraper (Colsubsidio)."""
from __future__ import annotations
from unittest.mock import patch, MagicMock
import pytest
import requests
from scraper import ColsubsidioScraper, SessionExpiredException

def test_scraper_init() -> None:
    """Verifica que el scraper configure las cookies de sesión correctamente."""
    scraper = ColsubsidioScraper(session_cookie="sess_123", csrf_token="csrf_abc")
    
    # Extraer cookies asociadas a la sesión
    cookies = scraper.session.cookies.get_dict()
    assert cookies.get("sistema") == "sess_123"
    assert cookies.get("Csrf-Token") == "csrf_abc"

@patch("requests.Session.post")
def test_fetch_available_dates_success(mock_post: MagicMock) -> None:
    """Verifica la extracción exitosa de fechas disponibles desde el calendario."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {
        "fechas": {
            "2026-06-10": {"fecha": "2026-06-10", "disponibilidad": True},
            "2026-06-11": {"fecha": "2026-06-11", "disponibilidad": False},
            "2026-06-12": {"fecha": "2026-06-12", "disponibilidad": True}
        }
    }
    mock_post.return_value = mock_response

    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")
    dates = scraper.fetch_available_dates(service_id=232)
    
    assert dates == ["2026-06-10", "2026-06-12"]
    mock_post.assert_called_once()

@patch("requests.Session.post")
def test_fetch_slots_for_date_success(mock_post: MagicMock) -> None:
    """Verifica el parseo correcto de cupos y horarios para una fecha dada."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {
        "horarios": [
            {
                "horario": {"hora_inicio": "18:00:00"},
                "duracion": 50,
                "zonas": [{"capacidad_disponible": 3}, {"capacidad_disponible": 1}]
            },
            {
                "horario": {"hora_inicio": "19:00:00"},
                "duracion": 50,
                "zonas": [{"capacidad_disponible": 0}]
            }
        ]
    }
    mock_post.return_value = mock_response

    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")
    slots = scraper.fetch_slots_for_date(service_id=232, date_str="2026-06-10")
    
    assert slots[0]["fecha"] == "2026-06-10"
    assert slots[0]["hora"] == "18:00"
    assert slots[0]["cupos"] == 4
    assert slots[0]["raw_horario"] == {"hora_inicio": "18:00:00"}
    assert slots[0]["zonas"] == [{"capacidad_disponible": 3}, {"capacidad_disponible": 1}]

@patch("requests.Session.post")
def test_session_expired_http_401(mock_post: MagicMock) -> None:
    """Verifica que se lance SessionExpiredException ante un código HTTP 401."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_post.return_value = mock_response

    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")
    with pytest.raises(SessionExpiredException):
        scraper.fetch_available_dates(service_id=232)

@patch("requests.Session.post")
def test_session_expired_json_unauthorized(mock_post: MagicMock) -> None:
    """Verifica que se lance SessionExpiredException ante un JSON con status Unauthorized."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {"status": "Unauthorized", "login": "redirect_url"}
    mock_post.return_value = mock_response

    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")
    with pytest.raises(SessionExpiredException):
        scraper.fetch_available_dates(service_id=232)

@patch("requests.Session.post")
def test_session_expired_html_redirect(mock_post: MagicMock) -> None:
    """Verifica que se lance SessionExpiredException ante una redirección HTML implícita."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_response.text = "<html><body>Debes loguearSitio para continuar</body></html>"
    mock_post.return_value = mock_response

    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")
    with pytest.raises(SessionExpiredException):
        scraper.fetch_available_dates(service_id=232)

@patch("requests.Session.post")
def test_resilience_on_server_error(mock_post: MagicMock) -> None:
    """Verifica que fallos de red o errores HTTP 500 no propaguen excepciones al loop principal."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_post.return_value = mock_response

    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")
    # No debe explotar, sino retornar una lista vacía de fechas o cupos
    assert scraper.fetch_available_dates(service_id=232) == []
    assert scraper.fetch_slots_for_date(service_id=232, date_str="2026-06-10") == []

@patch("requests.Session.post")
def test_resilience_on_timeout(mock_post: MagicMock) -> None:
    """Verifica tolerancia ante cortes de conexión."""
    mock_post.side_effect = requests.RequestException("Timeout")

    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")
    assert scraper.fetch_available_dates(service_id=232) == []

@patch("requests.Session.post")
def test_book_slot_success(mock_post: MagicMock) -> None:
    """Verifica que book_slot realice la reserva correctamente cuando el API responde 200."""
    mock_response_dispo = MagicMock()
    mock_response_dispo.status_code = 200
    mock_response_dispo.headers = {"Content-Type": "application/json"}
    mock_response_dispo.json.return_value = {
        "horarios": [
            {
                "horario": {"fecha": "2026-06-10", "hora_inicio": "18:00:00", "hora_fin": "18:50:00"},
                "duracion": 50,
                "zonas": [{"id": 12, "capacidad_disponible": 1}]
            }
        ]
    }
    
    mock_response_reserva = MagicMock()
    mock_response_reserva.status_code = 200
    mock_response_reserva.headers = {"Content-Type": "application/json"}
    mock_response_reserva.json.return_value = {
        "turnos_practica_libre": [
            {
                "id": 999
            }
        ]
    }
    
    mock_post.side_effect = [mock_response_dispo, mock_response_reserva]
    
    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")
    success, msg = scraper.book_slot(service_id=232, date_str="2026-06-10", time_str="18:00", tiquetera_id=6370683)
    
    assert success is True
    assert "éxito" in msg.lower()
    assert mock_post.call_count == 2

@patch("get_cookies.update_env_file")
@patch("get_cookies.extract_colsubsidio_cookies")
@patch("requests.Session.post")
def test_auto_retry_401_success(mock_post: MagicMock, mock_extract: MagicMock, mock_update_env: MagicMock) -> None:
    """Verifica la recuperación exitosa de un error HTTP 401 mediante renovación de sesión y reintento automático."""
    mock_response_401 = MagicMock()
    mock_response_401.status_code = 401

    mock_response_200 = MagicMock()
    mock_response_200.status_code = 200
    mock_response_200.headers = {"Content-Type": "application/json"}
    mock_response_200.json.return_value = {
        "fechas": {
            "2026-07-01": {"fecha": "2026-07-01", "disponibilidad": True}
        }
    }

    mock_post.side_effect = [mock_response_401, mock_response_200]
    mock_extract.return_value = {"sistema": "new_sess_token", "Csrf-Token": "new_csrf_token"}
    mock_update_env.return_value = True

    scraper = ColsubsidioScraper(session_cookie="old_sess", csrf_token="old_csrf")
    dates = scraper.fetch_available_dates(service_id=232)

    assert dates == ["2026-07-01"]
    assert mock_post.call_count == 2
    mock_extract.assert_called_once()
    mock_update_env.assert_called_once_with({"sistema": "new_sess_token", "Csrf-Token": "new_csrf_token"})
    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "new_sess_token"
    assert scraper.session.cookies.get("sitio", domain="www.diversioncolsubsidio.com") == "new_sess_token"
    assert scraper.session.cookies.get("Csrf-Token", domain="www.diversioncolsubsidio.com") == "new_csrf_token"
    assert scraper.session.headers.get("Csrf-Token") == "new_csrf_token"

@patch("get_cookies.update_env_file")
def test_in_memory_session_credentials_update(mock_update_env: MagicMock) -> None:
    """Verifica que update_session_credentials actualice las cookies e in-memory headers correctamente."""
    scraper = ColsubsidioScraper(session_cookie="init_sess", csrf_token="init_csrf")
    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "init_sess"
    assert scraper.session.headers.get("Csrf-Token") == "init_csrf"

    scraper.update_session_credentials({"sistema": "updated_sess", "Csrf-Token": "updated_csrf"})

    assert scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "updated_sess"
    assert scraper.session.cookies.get("sitio", domain="www.diversioncolsubsidio.com") == "updated_sess"
    assert scraper.session.cookies.get("Csrf-Token", domain="www.diversioncolsubsidio.com") == "updated_csrf"
    assert scraper.session.headers.get("Csrf-Token") == "updated_csrf"

@patch("get_cookies.update_env_file")
@patch("get_cookies.extract_colsubsidio_cookies")
@patch("requests.Session.post")
def test_persistent_401_raises_session_expired_exception(mock_post: MagicMock, mock_extract: MagicMock, mock_update_env: MagicMock) -> None:
    """Verifica que tras un 401 persistente en el reintento se re-lance SessionExpiredException."""
    mock_response_401 = MagicMock()
    mock_response_401.status_code = 401

    mock_post.return_value = mock_response_401
    mock_extract.return_value = {"sistema": "new_sess_token", "Csrf-Token": "new_csrf_token"}

    scraper = ColsubsidioScraper(session_cookie="old_sess", csrf_token="old_csrf")
    with pytest.raises(SessionExpiredException):
        scraper.fetch_available_dates(service_id=232)

    assert mock_post.call_count == 2
    mock_extract.assert_called_once()

@patch("get_cookies.extract_colsubsidio_cookies")
@patch("requests.Session.post")
def test_retry_failure_when_renewal_fails(mock_post: MagicMock, mock_extract: MagicMock) -> None:
    """Verifica que si la renovación de sesión no retorna cookies válidas se eleve SessionExpiredException inmediatamente."""
    mock_response_401 = MagicMock()
    mock_response_401.status_code = 401

    mock_post.return_value = mock_response_401
    mock_extract.return_value = {}

    scraper = ColsubsidioScraper(session_cookie="old_sess", csrf_token="old_csrf")
    with pytest.raises(SessionExpiredException):
        scraper.fetch_available_dates(service_id=232)

    assert mock_post.call_count == 1
    mock_extract.assert_called_once()

@patch("get_cookies.update_env_file")
@patch("get_cookies.extract_colsubsidio_cookies")
@patch("requests.Session.post")
def test_book_slot_auto_retry_success(mock_post: MagicMock, mock_extract: MagicMock, mock_update_env: MagicMock) -> None:
    """Verifica que book_slot recupere automáticamente un 401 en la petición de reservación."""
    mock_response_dispo = MagicMock()
    mock_response_dispo.status_code = 200
    mock_response_dispo.headers = {"Content-Type": "application/json"}
    mock_response_dispo.json.return_value = {
        "horarios": [
            {
                "horario": {"fecha": "2026-06-10", "hora_inicio": "18:00:00", "hora_fin": "18:50:00"},
                "duracion": 50,
                "zonas": [{"id": 12, "capacidad_disponible": 1}]
            }
        ]
    }

    mock_response_reserva_401 = MagicMock()
    mock_response_reserva_401.status_code = 401

    mock_response_reserva_200 = MagicMock()
    mock_response_reserva_200.status_code = 200
    mock_response_reserva_200.headers = {"Content-Type": "application/json"}
    mock_response_reserva_200.json.return_value = {
        "turnos_practica_libre": [{"id": 1001}]
    }

    mock_post.side_effect = [mock_response_dispo, mock_response_reserva_401, mock_response_reserva_200]
    mock_extract.return_value = {"sistema": "new_sess", "Csrf-Token": "new_csrf"}

    scraper = ColsubsidioScraper(session_cookie="old_sess", csrf_token="old_csrf")
    success, msg = scraper.book_slot(service_id=232, date_str="2026-06-10", time_str="18:00", tiquetera_id=123)

    assert success is True
    assert "éxito" in msg.lower()
    assert mock_post.call_count == 3
    mock_extract.assert_called_once()

