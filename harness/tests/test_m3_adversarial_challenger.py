"""Pruebas adversariales exhaustivas para la lógica de auto-sanación de Milestone 3 (code/scraper.py).

Cubre los 4 escenarios críticos requeridos por la auditoría de Challenger 1:
1. 401 persistentes (agotamiento de reintentos, comportamiento en fetch_available_dates y fetch_slots_for_date).
2. Respuestas JSON inesperadas / malformadas (status != "Unauthorized", respuestas tipo lista/primitivo, campos nulos/malformados).
3. Errores de red durante la renovación de sesión (exceptions en extract_colsubsidio_cookies()).
4. Reintentos y peticiones concurrentes (hilos simultáneos recibiendo 401).
"""
from __future__ import annotations

import concurrent.futures
import threading
import time
from unittest.mock import patch, MagicMock
import pytest
import requests

from scraper import ColsubsidioScraper, SessionExpiredException


# ============================================================================
# 1. PRUEBAS DE 401 PERSISTENTE Y AGOTAMIENTO DE REINTENTOS
# ============================================================================

@patch("get_cookies.update_env_file")
@patch("get_cookies.extract_colsubsidio_cookies")
@patch("requests.Session.post")
def test_persistent_401_in_fetch_available_dates(
    mock_post: MagicMock, mock_extract: MagicMock, mock_update_env: MagicMock
) -> None:
    """Verifica que si la API sigue retornando 401 tras la renovación, fetch_available_dates eleve SessionExpiredException."""
    mock_401 = MagicMock()
    mock_401.status_code = 401

    mock_post.return_value = mock_401
    mock_extract.return_value = {"sistema": "new_sess", "Csrf-Token": "new_csrf"}

    scraper = ColsubsidioScraper(session_cookie="old_sess", csrf_token="old_csrf")

    with pytest.raises(SessionExpiredException):
        scraper.fetch_available_dates(service_id=232)

    # Debe haber intentado exactamente 2 veces (1 inicial + 1 reintento)
    assert mock_post.call_count == 2
    mock_extract.assert_called_once()


@patch("get_cookies.update_env_file")
@patch("get_cookies.extract_colsubsidio_cookies")
@patch("requests.Session.post")
def test_persistent_401_in_fetch_slots_for_date(
    mock_post: MagicMock, mock_extract: MagicMock, mock_update_env: MagicMock
) -> None:
    """Verifica que si la API sigue retornando 401 tras la renovación, fetch_slots_for_date eleve SessionExpiredException."""
    mock_401 = MagicMock()
    mock_401.status_code = 401

    mock_post.return_value = mock_401
    mock_extract.return_value = {"sistema": "new_sess", "Csrf-Token": "new_csrf"}

    scraper = ColsubsidioScraper(session_cookie="old_sess", csrf_token="old_csrf")

    with pytest.raises(SessionExpiredException):
        scraper.fetch_slots_for_date(service_id=232, date_str="2026-08-10")

    assert mock_post.call_count == 2
    mock_extract.assert_called_once()



# ============================================================================
# 2. PRUEBAS DE CUERPOS JSON INESPERADOS Y MALFORMADOS
# ============================================================================

@patch("requests.Session.post")
def test_json_body_unauthorized_variants(mock_post: MagicMock) -> None:
    """Prueba si _check_unauthorized detecta variaciones de respuestas JSON no autorizadas (HTTP 200)."""
    # Caso A: {"status": "Unauthorized"} -> DEBE ser detectado según implementación actual
    r_auth = MagicMock()
    r_auth.status_code = 200
    r_auth.headers = {"Content-Type": "application/json"}
    r_auth.json.return_value = {"status": "Unauthorized"}

    # Caso B: {"error": "Unauthorized"} -> ¿Es detectado?
    r_err = MagicMock()
    r_err.status_code = 200
    r_err.headers = {"Content-Type": "application/json"}
    r_err.json.return_value = {"error": "Unauthorized"}

    # Caso C: {"status": 401} -> ¿Es detectado?
    r_status_int = MagicMock()
    r_status_int.status_code = 200
    r_status_int.headers = {"Content-Type": "application/json"}
    r_status_int.json.return_value = {"status": 401}

    # Caso D: {"code": "UNAUTHORIZED", "message": "Session expired"} -> ¿Es detectado?
    r_code = MagicMock()
    r_code.status_code = 200
    r_code.headers = {"Content-Type": "application/json"}
    r_code.json.return_value = {"code": "UNAUTHORIZED", "message": "Session expired"}

    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")

    # A debe lanzar SessionExpiredException
    mock_post.return_value = r_auth
    with pytest.raises(SessionExpiredException):
        scraper.fetch_available_dates(service_id=232)

    # Evaluar B, C, D (verificar que la comprobación defensiva mejorada detecte todas las variantes)
    for mock_r in [r_err, r_status_int, r_code]:
        mock_post.return_value = mock_r
        with pytest.raises(SessionExpiredException):
            scraper.fetch_available_dates(service_id=232)


@patch("requests.Session.post")
def test_json_body_is_list_handled_defensively(mock_post: MagicMock) -> None:
    """Verifica que la API retorne [] de forma segura cuando la respuesta JSON es una lista."""
    r_list = MagicMock()
    r_list.status_code = 200
    r_list.headers = {"Content-Type": "application/json"}
    r_list.json.return_value = []
    mock_post.return_value = r_list

    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")

    # En fetch_available_dates y fetch_slots_for_date, respuestas tipo lista se manejan sin excepciones
    assert scraper.fetch_available_dates(service_id=232) == []
    assert scraper.fetch_slots_for_date(service_id=232, date_str="2026-08-10") == []


@patch("requests.Session.post")
def test_json_body_fechas_is_none(mock_post: MagicMock) -> None:
    """Verifica qué ocurre cuando data es dict pero 'fechas' es None."""
    r_none = MagicMock()
    r_none.status_code = 200
    r_none.headers = {"Content-Type": "application/json"}
    r_none.json.return_value = {"fechas": None}
    mock_post.return_value = r_none

    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")

    # Manejo defensivo: 'fechas': None retorna [] sin elevación de excepciones
    assert scraper.fetch_available_dates(service_id=232) == []


@patch("requests.Session.post")
def test_json_body_malformed_horarios_elements(mock_post: MagicMock) -> None:
    """Verifica tolerancia ante elementos malformados o None dentro del arreglo 'horarios'."""
    r_malformed = MagicMock()
    r_malformed.status_code = 200
    r_malformed.headers = {"Content-Type": "application/json"}
    r_malformed.json.return_value = {
        "horarios": [
            None,
            {"horario": None},
            {"horario": {"hora_inicio": "10:00:00"}, "zonas": [None]}
        ]
    }
    mock_post.return_value = r_malformed

    scraper = ColsubsidioScraper(session_cookie="sess", csrf_token="csrf")

    # Manejo defensivo: filtra elementos nulos/malformados de horarios sin elevar excepciones
    slots = scraper.fetch_slots_for_date(service_id=232, date_str="2026-08-10")
    assert isinstance(slots, list)


# ============================================================================
# 3. ERRORES DE RED DURANTE LA RENOVACIÓN DE SESIÓN
# ============================================================================

@patch("get_cookies.extract_colsubsidio_cookies")
@patch("requests.Session.post")
def test_network_exception_during_session_renewal(
    mock_post: MagicMock, mock_extract: MagicMock
) -> None:
    """Verifica el comportamiento cuando extract_colsubsidio_cookies eleva un error de red o timeout."""
    mock_401 = MagicMock()
    mock_401.status_code = 401
    mock_post.return_value = mock_401

    # Simular falla de red durante la renovación de sesión
    mock_extract.side_effect = requests.RequestException("Connection timed out during browser cookie extraction")

    scraper = ColsubsidioScraper(session_cookie="old_sess", csrf_token="old_csrf")

    # En fetch_available_dates, RequestException es atrapado en la captura externa e imprime error, retornando []
    res = scraper.fetch_available_dates(service_id=232)
    assert res == []


@patch("get_cookies.extract_colsubsidio_cookies")
@patch("requests.Session.post")
def test_non_requests_exception_during_session_renewal(
    mock_post: MagicMock, mock_extract: MagicMock
) -> None:
    """Verifica el comportamiento cuando extract_colsubsidio_cookies eleva un error no-requests (ej. Playwright RuntimeError)."""
    mock_401 = MagicMock()
    mock_401.status_code = 401
    mock_post.return_value = mock_401

    # Simular falla de Playwright / sistema durante la renovación
    mock_extract.side_effect = RuntimeError("Playwright browser executable not found")

    scraper = ColsubsidioScraper(session_cookie="old_sess", csrf_token="old_csrf")

    # RuntimeError es capturado y envuelto en SessionExpiredException
    with pytest.raises(SessionExpiredException):
        scraper.fetch_available_dates(service_id=232)


# ============================================================================
# 4. PETICIONES Y REINTENTOS CONCURRENTES (RACE CONDITIONS)
# ============================================================================

@patch("get_cookies.update_env_file")
@patch("get_cookies.extract_colsubsidio_cookies")
@patch("requests.Session.post")
def test_concurrent_requests_triggering_session_renewal(
    mock_post: MagicMock, mock_extract: MagicMock, mock_update_env: MagicMock
) -> None:
    """Prueba el comportamiento de hilos concurrentes que reciben 401 simultáneamente usando la misma instancia de scraper."""
    mock_401 = MagicMock()
    mock_401.status_code = 401

    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.headers = {"Content-Type": "application/json"}
    mock_200.json.return_value = {"fechas": {"2026-08-15": {"disponibilidad": True}}}

    renewal_counter = 0
    renewal_lock = threading.Lock()

    def slow_extract():
        nonlocal renewal_counter
        with renewal_lock:
            renewal_counter += 1
            cnt = renewal_counter
        time.sleep(0.05)  # Simular latencia de apertura de navegador Playwright
        return {"sistema": f"sess_renewed_{cnt}", "Csrf-Token": f"csrf_renewed_{cnt}"}

    mock_extract.side_effect = slow_extract

    # Para cada hilo: primera respuesta 401, segunda 200
    # Como hay múltiples hilos, simulamos que 401 ocurre en el primer intento de cada hilo
    def post_side_effect(*args, **kwargs):
        # Si el token actual es 'old_sess', retorna 401. Si es renovado, retorna 200.
        cookies = kwargs.get("cookies") or {}
        # requests.Session pasa cookies en la sesión
        current_sess = scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com")
        if current_sess == "old_sess":
            return mock_401
        return mock_200

    mock_post.side_effect = post_side_effect

    scraper = ColsubsidioScraper(session_cookie="old_sess", csrf_token="old_csrf")

    num_threads = 4
    results = []

    def worker_task(venue_id):
        res = scraper.fetch_available_dates(service_id=venue_id)
        results.append(res)

    threads = [threading.Thread(target=worker_task, args=(230 + i,)) for i in range(num_threads)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Documentar los hallazgos de concurrencia:
    # ¿Cuántas veces se llamó a extract_colsubsidio_cookies()?
    # Si renewal_counter > 1, indica que no hay mutex/candado en la renovación y se lanzan múltiples extracciones redundantes.
    print(f"Total renovaciones ejecutadas para {num_threads} hilos simultáneos: {renewal_counter}")
    assert len(results) == num_threads
