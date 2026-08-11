"""Script de verificación empírica de fallas para Milestone 3 (scraper.py)."""
import os
import sys
import threading
import time
from unittest.mock import patch, MagicMock
import requests

# Asegurar import de code/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../code")))

from scraper import ColsubsidioScraper, SessionExpiredException

def test_empiric_1_book_slot_uncaught_exception():
    """Empirical check 1: book_slot raises SessionExpiredException on persistent 401, breaking return contract."""
    print("--- Testing Empirical 1: book_slot uncaught SessionExpiredException ---")
    mock_dispo_200 = MagicMock()
    mock_dispo_200.status_code = 200
    mock_dispo_200.headers = {"Content-Type": "application/json"}
    mock_dispo_200.json.return_value = {
        "horarios": [{"horario": {"fecha": "2026-08-10", "hora_inicio": "18:00:00"}, "zonas": [{"id": 1, "capacidad_disponible": 1}]}]
    }
    mock_reserva_401 = MagicMock()
    mock_reserva_401.status_code = 401

    scraper = ColsubsidioScraper("sess", "csrf")

    with patch("requests.Session.post", side_effect=[mock_dispo_200, mock_reserva_401, mock_reserva_401]), \
         patch("get_cookies.extract_colsubsidio_cookies", return_value={"sistema": "new", "Csrf-Token": "new"}), \
         patch("get_cookies.update_env_file"):
        try:
            res = scraper.book_slot(232, "2026-08-10", "18:00", 123)
            print("FAILED: Did not raise exception, returned:", res)
        except SessionExpiredException as e:
            print(f"CONFIRMED: book_slot raised uncaught SessionExpiredException: '{e}' instead of returning (False, msg)")

def test_empiric_2_json_list_attribute_error():
    """Empirical check 2: JSON list body causes unhandled AttributeError in fetch_available_dates."""
    print("\n--- Testing Empirical 2: JSON list body causing AttributeError ---")
    mock_list_200 = MagicMock()
    mock_list_200.status_code = 200
    mock_list_200.headers = {"Content-Type": "application/json"}
    mock_list_200.json.return_value = [{"error": "invalid session"}]

    scraper = ColsubsidioScraper("sess", "csrf")

    with patch("requests.Session.post", return_value=mock_list_200):
        try:
            res = scraper.fetch_available_dates(232)
            print("Result:", res)
        except AttributeError as e:
            print(f"CONFIRMED: fetch_available_dates crashed with unhandled AttributeError: '{e}'")

def test_empiric_3_unauthorized_json_variants_missed():
    """Empirical check 3: JSON response with status=401 or error=Unauthorized missed by _check_unauthorized."""
    print("\n--- Testing Empirical 3: Unauthorized JSON variants missed ---")
    mock_err_200 = MagicMock()
    mock_err_200.status_code = 200
    mock_err_200.headers = {"Content-Type": "application/json"}
    mock_err_200.json.return_value = {"error": "Unauthorized", "message": "Token expired"}

    scraper = ColsubsidioScraper("sess", "csrf")

    with patch("requests.Session.post", return_value=mock_err_200):
        try:
            res = scraper.fetch_available_dates(232)
            print(f"CONFIRMED: fetch_available_dates missed unauthorized error payload and returned empty list: {res}")
        except SessionExpiredException:
            print("FAILED: SessionExpiredException was raised")

def test_empiric_4_renewal_non_requests_exception():
    """Empirical check 4: Non-requests exception in extract_colsubsidio_cookies crashes fetch_available_dates."""
    print("\n--- Testing Empirical 4: Playwright exception during renewal crashing fetch_available_dates ---")
    mock_401 = MagicMock()
    mock_401.status_code = 401

    scraper = ColsubsidioScraper("sess", "csrf")

    with patch("requests.Session.post", return_value=mock_401), \
         patch("get_cookies.extract_colsubsidio_cookies", side_effect=RuntimeError("Playwright Chromium launch failure")):
        try:
            res = scraper.fetch_available_dates(232)
            print("Result:", res)
        except RuntimeError as e:
            print(f"CONFIRMED: fetch_available_dates crashed with unhandled RuntimeError: '{e}'")

def test_empiric_5_concurrent_renewal_stampede():
    """Empirical check 5: Concurrent 401 requests cause multiple redundant cookie extractions."""
    print("\n--- Testing Empirical 5: Concurrent renewal stampede ---")
    mock_401 = MagicMock()
    mock_401.status_code = 401

    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.headers = {"Content-Type": "application/json"}
    mock_200.json.return_value = {"fechas": {"2026-08-15": {"disponibilidad": True}}}

    extraction_count = 0
    lock = threading.Lock()

    def mock_extract():
        nonlocal extraction_count
        with lock:
            extraction_count += 1
        time.sleep(0.02)
        return {"sistema": "new_sess", "Csrf-Token": "new_csrf"}

    scraper = ColsubsidioScraper("old_sess", "old_csrf")

    def post_side_effect(*args, **kwargs):
        if scraper.session.cookies.get("sistema", domain="www.diversioncolsubsidio.com") == "old_sess":
            return mock_401
        return mock_200

    with patch("requests.Session.post", side_effect=post_side_effect), \
         patch("get_cookies.extract_colsubsidio_cookies", side_effect=mock_extract), \
         patch("get_cookies.update_env_file"):
        
        threads = [threading.Thread(target=scraper.fetch_available_dates, args=(230 + i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        print(f"CONFIRMED: 4 concurrent 401 requests triggered {extraction_count} redundant cookie extractions (no lock)")

if __name__ == "__main__":
    test_empiric_1_book_slot_uncaught_exception()
    test_empiric_2_json_list_attribute_error()
    test_empiric_3_unauthorized_json_variants_missed()
    test_empiric_4_renewal_non_requests_exception()
    test_empiric_5_concurrent_renewal_stampede()
