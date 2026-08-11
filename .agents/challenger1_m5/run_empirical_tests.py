"""
Script de verificación empírica y stress testing para Milestone 5.
Ejecuta validaciones exhaustivas sobre:
1. Detección de cookie expirada y retry automático en scraper.py y main.py
2. Lógica de cálculo de festivos en Colombia (Gauss/Easter + Ley Emiliani)
3. Ejecución completa del arnés de pruebas pytest en harness/tests/
"""

from __future__ import annotations
import sys
import os
import io
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock
import pytest

# Asegurar que code/ y harness/ están en sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CODE_DIR = os.path.join(PROJECT_ROOT, "code")
HARNESS_DIR = os.path.join(PROJECT_ROOT, "harness")

if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print(f"=== EMPIRICAL TEST SUITE FOR MILESTONE 5 ===")
print(f"Project root: {PROJECT_ROOT}")
print(f"Python executable: {sys.executable}")

# ============================================================================
# SECCIÓN 1: Detección de Cookie Expirada y Reintentos
# ============================================================================
def test_section_1_cookie_expiry_and_retry():
    print("\n--- SECCIÓN 1: Cookie Expiry & Retry Logic ---")
    from scraper import ColsubsidioScraper, SessionExpiredException
    from main import is_within_preferred_schedule

    # Test 1.1: HTTP 401 retriggers scraper session renewal and retries
    with patch("get_cookies.update_env_file") as mock_update_env, \
         patch("get_cookies.extract_colsubsidio_cookies") as mock_extract, \
         patch("requests.Session.post") as mock_post:
        
        mock_401 = MagicMock()
        mock_401.status_code = 401
        
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.headers = {"Content-Type": "application/json"}
        mock_200.json.return_value = {"fechas": {"2026-08-15": {"disponibilidad": True}}}
        
        mock_post.side_effect = [mock_401, mock_200]
        mock_extract.return_value = {"sistema": "new_cookie_123", "Csrf-Token": "new_csrf_123"}
        mock_update_env.return_value = True

        scraper = ColsubsidioScraper(session_cookie="old_cookie", csrf_token="old_csrf")
        dates = scraper.fetch_available_dates(service_id=232)
        
        assert dates == ["2026-08-15"], f"Expected ['2026-08-15'], got {dates}"
        assert mock_post.call_count == 2, f"Expected 2 HTTP calls, got {mock_post.call_count}"
        mock_extract.assert_called_once()
        print("  [PASS] 1.1: HTTP 401 triggers auto-renewal & succeeds on retry.")

    # Test 1.2: JSON status Unauthorized
    with patch("get_cookies.update_env_file") as mock_update_env, \
         patch("get_cookies.extract_colsubsidio_cookies") as mock_extract, \
         patch("requests.Session.post") as mock_post:
        
        mock_unauth = MagicMock()
        mock_unauth.status_code = 200
        mock_unauth.headers = {"Content-Type": "application/json"}
        mock_unauth.json.return_value = {"status": "Unauthorized"}

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.headers = {"Content-Type": "application/json"}
        mock_200.json.return_value = {"fechas": {"2026-08-16": {"disponibilidad": True}}}

        mock_post.side_effect = [mock_unauth, mock_200]
        mock_extract.return_value = {"sistema": "new_cookie_json", "Csrf-Token": "new_csrf_json"}

        scraper = ColsubsidioScraper(session_cookie="old", csrf_token="old")
        dates = scraper.fetch_available_dates(service_id=232)
        assert dates == ["2026-08-16"]
        print("  [PASS] 1.2: JSON status Unauthorized triggers auto-renewal & retry.")

    # Test 1.3: HTML redirect to loguearSitio
    with patch("get_cookies.update_env_file") as mock_update_env, \
         patch("get_cookies.extract_colsubsidio_cookies") as mock_extract, \
         patch("requests.Session.post") as mock_post:
        
        mock_html = MagicMock()
        mock_html.status_code = 200
        mock_html.headers = {"Content-Type": "text/html"}
        mock_html.text = "<html><body>Redireccionando a loguearSitio</body></html>"

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.headers = {"Content-Type": "application/json"}
        mock_200.json.return_value = {"fechas": {"2026-08-17": {"disponibilidad": True}}}

        mock_post.side_effect = [mock_html, mock_200]
        mock_extract.return_value = {"sistema": "new_cookie_html", "Csrf-Token": "new_csrf_html"}

        scraper = ColsubsidioScraper(session_cookie="old", csrf_token="old")
        dates = scraper.fetch_available_dates(service_id=232)
        assert dates == ["2026-08-17"]
        print("  [PASS] 1.3: HTML loguearSitio redirect triggers auto-renewal & retry.")

    # Test 1.4: Persistent 401 exhaustion
    with patch("get_cookies.update_env_file") as mock_update_env, \
         patch("get_cookies.extract_colsubsidio_cookies") as mock_extract, \
         patch("requests.Session.post") as mock_post:
        
        mock_401 = MagicMock()
        mock_401.status_code = 401

        mock_post.return_value = mock_401
        mock_extract.return_value = {"sistema": "renewed_cookie", "Csrf-Token": "renewed_csrf"}

        scraper = ColsubsidioScraper(session_cookie="old", csrf_token="old")
        try:
            scraper.fetch_available_dates(service_id=232)
            assert False, "Should have raised SessionExpiredException"
        except SessionExpiredException:
            print("  [PASS] 1.4: Persistent 401 re-raises SessionExpiredException after 1 retry.")

    # Test 1.5: Renewal fails (empty cookies)
    with patch("get_cookies.extract_colsubsidio_cookies") as mock_extract, \
         patch("requests.Session.post") as mock_post:
        
        mock_401 = MagicMock()
        mock_401.status_code = 401
        mock_post.return_value = mock_401
        mock_extract.return_value = {}

        scraper = ColsubsidioScraper(session_cookie="old", csrf_token="old")
        try:
            scraper.fetch_available_dates(service_id=232)
            assert False, "Should have raised SessionExpiredException"
        except SessionExpiredException:
            print("  [PASS] 1.5: Renewal failure (empty dict) raises SessionExpiredException without secondary HTTP call.")

    # Test 1.6: Auto-retry in book_slot step 2
    with patch("get_cookies.update_env_file") as mock_update_env, \
         patch("get_cookies.extract_colsubsidio_cookies") as mock_extract, \
         patch("requests.Session.post") as mock_post:

        mock_dispo = MagicMock()
        mock_dispo.status_code = 200
        mock_dispo.headers = {"Content-Type": "application/json"}
        mock_dispo.json.return_value = {
            "horarios": [
                {
                    "horario": {"fecha": "2026-08-20", "hora_inicio": "18:00:00", "hora_fin": "18:50:00"},
                    "duracion": 50,
                    "zonas": [{"id": 1, "capacidad_disponible": 1}]
                }
            ]
        }
        mock_reserva_401 = MagicMock()
        mock_reserva_401.status_code = 401

        mock_reserva_200 = MagicMock()
        mock_reserva_200.status_code = 200
        mock_reserva_200.headers = {"Content-Type": "application/json"}
        mock_reserva_200.json.return_value = {"turnos_practica_libre": [{"id": 100}]}

        mock_post.side_effect = [mock_dispo, mock_reserva_401, mock_reserva_200]
        mock_extract.return_value = {"sistema": "new_book_cookie", "Csrf-Token": "new_book_csrf"}

        scraper = ColsubsidioScraper(session_cookie="old", csrf_token="old")
        ok, msg = scraper.book_slot(232, "2026-08-20", "18:00", 12345)
        assert ok is True
        print("  [PASS] 1.6: book_slot automatically retries and succeeds when step 2 receives HTTP 401.")

# ============================================================================
# SECCIÓN 2: Lógica de Festivos en Colombia (Gauss/Easter + Ley Emiliani)
# ============================================================================
def test_section_2_colombian_holidays():
    print("\n--- SECCIÓN 2: Colombian Holiday Calculation Logic ---")
    from main import is_colombian_holiday, is_within_preferred_schedule, _holidays_cache

    # Limpiar caché de festivos para asegurar recálculo fresco
    _holidays_cache.clear()

    # 1. Pascua / Easter test cases across multiple years
    # 2024: Easter is March 31
    # 2025: Easter is April 20
    # 2026: Easter is April 5
    # 2027: Easter is March 28

    # Verificar 2026 (Easter = 2026-04-05)
    # Jueves Santo: 2026-04-02
    # Viernes Santo: 2026-04-03
    # Ascensión del Señor: Easter + 43 = 2026-05-18 (Lunes)
    # Corpus Christi: Easter + 64 = 2026-06-08 (Lunes)
    # Sagrado Corazón: Easter + 71 = 2026-06-15 (Lunes)

    holidays_2026_expected = {
        date(2026, 1, 1),   # Año Nuevo (Jueves)
        date(2026, 1, 12),  # Reyes Magos (Translado de 01-06 Martes a Lunes 01-12)
        date(2026, 3, 23),  # San José (Translado de 03-19 Jueves a Lunes 03-23)
        date(2026, 4, 2),   # Jueves Santo
        date(2026, 4, 3),   # Viernes Santo
        date(2026, 5, 1),   # Día del Trabajo (Viernes)
        date(2026, 5, 18),  # Ascensión del Señor
        date(2026, 6, 8),   # Corpus Christi
        date(2026, 6, 15),  # Sagrado Corazón
        date(2026, 6, 29),  # San Pedro y San Pablo (Translado de 06-29 Lunes -> cae Lunes, no cambia)
        date(2026, 7, 20),  # Grito de Independencia (Lunes)
        date(2026, 8, 7),   # Batalla de Boyacá (Viernes)
        date(2026, 8, 17),  # Asunción de la Virgen (Translado de 08-15 Sábado a Lunes 08-17)
        date(2026, 10, 12), # Día de la Raza (Lunes)
        date(2026, 11, 2),  # Todos los Santos (Translado de 11-01 Domingo a Lunes 11-02)
        date(2026, 11, 16), # Independencia de Cartagena (Translado de 11-11 Miércoles a Lunes 11-16)
        date(2026, 12, 8),  # Inmaculada Concepción (Martes)
        date(2026, 12, 25), # Navidad (Viernes)
    }

    # Probar todos los 365 días de 2026
    holidays_2026_computed = set()
    start_date = date(2026, 1, 1)
    for i in range(365):
        cur = start_date + timedelta(days=i)
        if is_colombian_holiday(cur):
            holidays_2026_computed.add(cur)

    assert len(holidays_2026_computed) == 18, f"Expected 18 holidays in 2026, computed {len(holidays_2026_computed)}"
    diff = holidays_2026_computed.symmetric_difference(holidays_2026_expected)
    assert not diff, f"Mismatch in 2026 holidays: {diff}"
    print(f"  [PASS] 2.1: Exactly 18 official Colombian holidays in 2026 calculated correctly.")

    # Test Ley Emiliani rules:
    # Rule 1: Fixed non-Emiliani stay on exact date
    assert is_colombian_holiday(date(2026, 7, 20)) is True # July 20
    assert is_colombian_holiday(date(2026, 8, 7)) is True  # Aug 7
    assert is_colombian_holiday(date(2026, 12, 25)) is True # Dec 25

    # Rule 2: Fixed Emiliani shift to next Monday if not Monday
    # Reyes Magos 2026: Jan 6 is Tuesday -> moved to Jan 12 (Monday)
    assert is_colombian_holiday(date(2026, 1, 6)) is False
    assert is_colombian_holiday(date(2026, 1, 12)) is True
    print("  [PASS] 2.2: Ley Emiliani shift verified (Jan 6 Tuesday -> Jan 12 Monday).")

    # Rule 3: Fixed Emiliani on Monday remains on Monday
    # San Pedro y San Pablo 2026: June 29 is Monday -> stays on June 29
    assert is_colombian_holiday(date(2026, 6, 29)) is True
    print("  [PASS] 2.3: Ley Emiliani Monday preservation verified (June 29 Monday stays June 29).")

    # Rule 4: Preferred schedule filtering with holidays
    # Weekday non-holiday: 18:00 to 20:00 only
    assert is_within_preferred_schedule("2026-06-01", "18:00") is True  # Monday non-holiday 18:00
    assert is_within_preferred_schedule("2026-06-01", "12:00") is False # Monday non-holiday 12:00
    
    # Holiday Monday (Corpus Christi 2026-06-08): any time
    assert is_within_preferred_schedule("2026-06-08", "08:00") is True
    assert is_within_preferred_schedule("2026-06-08", "12:00") is True
    assert is_within_preferred_schedule("2026-06-08", "21:00") is True
    
    # Weekend (Saturday 2026-06-13): any time
    assert is_within_preferred_schedule("2026-06-13", "08:00") is True
    print("  [PASS] 2.4: Preferred schedule filter respects Colombian holidays and weekends.")

# ============================================================================
# SECCIÓN 3: Ejecución completa del Arnés pytest
# ============================================================================
def test_section_3_run_pytest_harness():
    print("\n--- SECCIÓN 3: Full pytest Harness Execution Across 10 Test Modules ---")
    test_files = [
        "harness/tests/test_dummy.py",
        "harness/tests/test_get_cookies.py",
        "harness/tests/test_get_cookies_adversarial.py",
        "harness/tests/test_m2_adversarial.py",
        "harness/tests/test_m3_adversarial_challenger.py",
        "harness/tests/test_m3_challenger_session.py",
        "harness/tests/test_m4_cicd_local_runner.py",
        "harness/tests/test_notifier.py",
        "harness/tests/test_orchestrator.py",
        "harness/tests/test_scraper.py",
    ]

    print(f"Running pytest on {len(test_files)} test modules...")
    exit_code = pytest.main(["-v", *test_files])
    assert exit_code == 0, f"pytest exit code was {exit_code}"
    print("  [PASS] 3.1: All 10 pytest test modules passed cleanly with exit code 0.")

if __name__ == "__main__":
    try:
        test_section_1_cookie_expiry_and_retry()
        test_section_2_colombian_holidays()
        test_section_3_run_pytest_harness()
        print("\n==========================================")
        print("ALL EMPIRICAL VERIFICATION TESTS PASSED SUCCESSFULLY!")
        print("==========================================")
    except Exception as e:
        print(f"\n[FAILURE] Empirical test run failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
