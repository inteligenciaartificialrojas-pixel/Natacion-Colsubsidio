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
    
    assert len(slots) == 1
    assert slots[0] == {"fecha": "2026-06-10", "hora": "18:00", "cupos": 4}

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
