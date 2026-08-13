# Implementation Instructions for Worker: Milestone 1 Test Suite & Unit Test Clean-up

## Executive Summary
Milestone 1 focuses on two primary features:
1. **F1: Cookie Session Scraper Refactoring**: Query availability endpoints (`/v1/centro_entrenamiento/{id}/practicalibre/calendario` and `disponibilidad`) using `COLSUBSIDIO_SISTEMA_COOKIE` and `COLSUBSIDIO_CSRF_TOKEN` headers, with HTTP 401 session expiration handling (`SessionExpiredException`) and Playwright-based automatic cookie renewal.
2. **F2: Legacy Reservation Code Removal**: Complete removal of all booking, reservation, and tiquetera logic (`book_slot()`, Telegram `/agendar` command parser, `COLSUBSIDIO_TIQUETERA_ID`, and associated unit test cases).

This analysis provides exact step-by-step instructions for refactoring the test suite (`harness/tests/test_scraper.py`, `harness/tests/test_notifier.py`, `harness/tests/test_get_cookies.py`) and corresponding source code files.

---

## 1. Test Suite Cleanup Instructions

### A. `harness/tests/test_scraper.py`
- **File Location**: `j:\Mi unidad\Natacion Colsubsidio\harness\tests\test_scraper.py`
- **Actions Required**:
  1. **Delete Legacy Reservation Test Cases**:
     - Remove `test_book_slot_success` (lines 128–161 in current file).
     - Remove `test_book_slot_auto_retry_success` (lines 248–283 in current file).
  2. **Retain and Verify Active Scraper Test Cases**:
     - `test_scraper_init()`: Confirms initialization sets `sistema` and `Csrf-Token` session cookies.
     - `test_fetch_available_dates_success()`: Mocks `requests.Session.post` for endpoint `.../calendario` and verifies extracted date list `["2026-06-10", "2026-06-12"]`.
     - `test_fetch_slots_for_date_success()`: Mocks `requests.Session.post` for endpoint `.../disponibilidad?filtrarSinCupo=0` and verifies slot parsing (`fecha`, `hora`, `cupos`, `raw_horario`, `zonas`).
     - `test_session_expired_http_401()`: Verifies HTTP 401 raises `SessionExpiredException`.
     - `test_session_expired_json_unauthorized()`: Verifies JSON response `{"status": "Unauthorized"}` raises `SessionExpiredException`.
     - `test_session_expired_html_redirect()`: Verifies HTML response containing `loguearSitio` raises `SessionExpiredException`.
     - `test_resilience_on_server_error()`: Verifies HTTP 500 returns empty list `[]` without crashing.
     - `test_resilience_on_timeout()`: Verifies `requests.RequestException` returns empty list `[]`.
     - `test_auto_retry_401_success()`: Verifies auto-retry flow upon HTTP 401 via `extract_colsubsidio_cookies()` and `update_env_file()`, updating session headers & cookies in memory.
     - `test_in_memory_session_credentials_update()`: Verifies `update_session_credentials()` sets cookies for domain `www.diversioncolsubsidio.com` & `.diversioncolsubsidio.com` and header `Csrf-Token`.
     - `test_persistent_401_raises_session_expired_exception()`: Verifies persistent HTTP 401 after retry re-raises `SessionExpiredException`.
     - `test_retry_failure_when_renewal_fails()`: Verifies failed renewal re-raises `SessionExpiredException` immediately.

### B. `harness/tests/test_notifier.py`
- **File Location**: `j:\Mi unidad\Natacion Colsubsidio\harness\tests\test_notifier.py`
- **Actions Required**:
  1. **Delete Legacy Interactive Command Test Case**:
     - Remove `test_get_incoming_commands_success` (lines 114–142 in current file).
  2. **Retain and Verify Active Notifier Test Cases**:
     - `test_notifier_init()`: Confirms initialization with token and chat_id.
     - `test_send_message_missing_credentials()`: Confirms returns `False` when credentials missing.
     - `test_send_message_success()`: Confirms Markdown payload posted to Telegram API.
     - `test_send_message_http_error()`: Confirms HTTP errors return `False`.
     - `test_send_message_network_error()`: Confirms network exceptions return `False`.
     - `test_notify_venue_slots_deduplication()`: Confirms deduplication supresses identical alerts within cache window.
     - `test_notify_venue_slots_expiration()`: Confirms cache expiry re-notifies after configured duration.
  3. **Clean Notification Format Verification**:
     - Ensure tests assert clean text format without `/agendar_...` interactive command links.

### C. `harness/tests/test_get_cookies.py`
- **File Location**: `j:\Mi unidad\Natacion Colsubsidio\harness\tests\test_get_cookies.py`
- **Actions Required**:
  - Retain all 8 test cases intact. All tests in this module cover Playwright login authentication, cookie extraction, `.env` file updating, and OS-specific fallbacks (F1/R1 requirements).

---

## 2. Complementary Source Code Purge Instructions

To ensure test suite execution passes cleanly without dead imports or references, Worker must apply corresponding changes in `code/`:

1. **`code/scraper.py`**:
   - Delete `ColsubsidioScraper.book_slot()` method (lines 245–345).

2. **`code/notifier.py`**:
   - Delete `TelegramNotifier.get_incoming_commands()` method (lines 75–104).
   - In `TelegramNotifier.notify_venue_slots()`: Remove `/agendar_...` command string generation (lines 184–188). Format slot line cleanly as: `• ⏰ \`{s['hora']}\` 🎟️ \`{s['cupos']}\` cupos`.

3. **`code/config.py`**:
   - Delete `COLSUBSIDIO_TIQUETERA_ID` and `_tiq_val` configuration (lines 31–33).

4. **`code/main.py`**:
   - Remove section 1 (interactive command processing loop checking `get_incoming_commands()` and executing `/agendar` via `book_slot()`) (lines 229–280).

---

## 3. Verification Checklist for Worker
- [ ] `pytest harness/tests/test_scraper.py` runs and passes 100% of remaining 12 tests.
- [ ] `pytest harness/tests/test_notifier.py` runs and passes 100% of remaining 7 tests.
- [ ] `pytest harness/tests/test_get_cookies.py` runs and passes 100% of 8 tests.
- [ ] No references to `book_slot`, `get_incoming_commands`, or `COLSUBSIDIO_TIQUETERA_ID` remain in `code/` or `harness/tests/`.
