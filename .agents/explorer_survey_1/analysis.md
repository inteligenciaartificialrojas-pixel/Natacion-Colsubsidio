# Analysis Report: Codebase Survey & Requirement Mapping

**Author**: `teamwork_preview_explorer`  
**Date**: 2026-08-11  
**Project**: Colsubsidio Swimming Availability Monitor (`j:\Mi unidad\Natacion Colsubsidio`)

---

## 1. Executive Summary

This report maps the current codebase structure, Python modules, dependencies, testing setup, CI/CD pipeline, legacy reservation/tiquetera components scheduled for removal, and the API scraper implementation against the updated user requirements (2026-08-12 specification).

Key Findings:
1. **Clean Modular Architecture**: Python core located under `code/` with CLI orchestration (`main.py`), Playwright login helper (`get_cookies.py`), API client with self-healing retry (`scraper.py`), Telegram alert module (`notifier.py`), and background cookie sync daemon (`daemon.py`).
2. **Legacy Code Identified**: Reservation logic (`book_slot()` in `scraper.py`), interactive `/agendar` command handlers in `main.py` and `notifier.py`, and `COLSUBSIDIO_TIQUETERA_ID` in `config.py` and `.github/workflows/check.yml` must be cleanly removed to align with the read-only availability monitoring scope.
3. **Schedule Filter Refactoring Required**: Current schedule filter allows weekdays 18:00–20:00. Updated requirement R2 specifies weekdays before 7:00 AM (`< 07:00`) or after 5:00 PM (`>= 17:00`), and weekends/holidays all day (24h).
4. **CI/CD Alignment**: `.github/workflows/check.yml` currently runs on a 10-minute cron (`*/10 * * * *`); requirement R4 requires a 20-minute cron (`*/20 * * * *`).

---

## 2. Directory and File Structure Map

```
j:\Mi unidad\Natacion Colsubsidio/
├── PROJECT.md                             # Architectural overview & milestone status
├── actualizar_cookies.bat                 # Helper script to manual trigger get_cookies.py
├── ejecutar_revisor_local.bat             # Helper script to run local monitor loop
├── instalar_daemon.bat                    # Windows Task Scheduler installer for daemon.py
├── run_daemon_silent.vbs                  # VBS wrapper for silent background daemon execution
├── daemon.log                             # Log output for background cookie daemon
├── .cooldown_state                        # JSON state file tracking last report timestamp & update IDs
├── .last_slots.json                       # JSON cache of previous scan slot states for de-duplication
├── .env.example                           # Template for required environment variables
├── .env                                   # Local runtime environment file (gitignored)
├── .gitignore                             # Git ignore specifications
├── .github/
│   └── workflows/
│       └── check.yml                      # GitHub Actions workflow (Cron & Workflow Dispatch)
├── code/
│   ├── config.py                          # Environment loading, venue IDs, & schedule constants
│   ├── scraper.py                         # API client & HTTP 401 SessionExpired retry logic
│   ├── get_cookies.py                     # Playwright Chromium automated login & local cookie extraction
│   ├── main.py                            # CLI entry point, schedule filter engine, & loop
│   ├── notifier.py                        # Telegram notification formatting & cache de-duplication
│   ├── daemon.py                          # Background script for syncing cookies to GitHub Secrets
│   └── requirements.txt                   # Dependency list
└── harness/
    ├── conftest.py                        # Pytest fixtures and shared configuration
    ├── feature_list.json                  # Harness feature inventory
    ├── specs/                             # Feature specifications (scraper, orchestrator, notifier)
    └── tests/                             # Test suite directory
        ├── test_dummy.py
        ├── test_get_cookies.py            # Unit tests for Playwright login & .env sync
        ├── test_get_cookies_adversarial.py # Stress tests for cookie extraction
        ├── test_m2_adversarial.py         # Malformed env & credential edge cases
        ├── test_m3_adversarial_challenger.py # 401 retry & response edge cases
        ├── test_m3_challenger_session.py  # Session resilience tests
        ├── test_m4_cicd_local_runner.py   # CI/CD and runner script integrity tests
        ├── test_notifier.py               # Unit tests for Telegram notifier
        ├── test_orchestrator.py           # Unit tests for schedule filtering & main orchestrator
        └── test_scraper.py                # Unit tests for scraper endpoints & 401 handling
```

---

## 3. Existing Python Scripts & Module Responsibilities

| File | Purpose / Responsibilities | Key Functions / Classes |
|---|---|---|
| `code/config.py` | Environment loading, venue mappings, schedule preferences | `PREFERRED_VENUES`, `VENUE_SERVICE_IDS`, `TELEGRAM_*`, `COLSUBSIDIO_*` |
| `code/scraper.py` | API interaction with Colsubsidio backend, 401 session expiration handling, automatic retry | `ColsubsidioScraper`, `SessionExpiredException`, `fetch_available_dates()`, `fetch_slots_for_date()`, `_renew_session()`, `book_slot()` (LEGACY) |
| `code/get_cookies.py` | Automated browser login via Playwright Chromium, cookie extraction (`sistema`, `Csrf-Token`), atomic `.env` update | `login_and_get_cookies()`, `extract_local_browser_cookies()`, `extract_colsubsidio_cookies()`, `update_env_file()`, `sync_secrets_to_github()` |
| `code/main.py` | Main execution loop, state persistence, Colombian holiday engine, schedule filter engine | `main()`, `check_venues()`, `is_within_preferred_schedule()`, `is_colombian_holiday()`, `find_new_slots()`, `load_cooldown_state()`, `save_cooldown_state()` |
| `code/notifier.py` | Telegram notification formatting, deduplication cache | `TelegramNotifier`, `notify_venue_slots()`, `send_message()`, `get_incoming_commands()` (LEGACY) |
| `code/daemon.py` | Background daemon to extract cookies and update GitHub secrets via `gh CLI` | `run_daemon_sync()` |

---

## 4. Dependencies & Environment Configuration

### Python Dependencies (`code/requirements.txt`)
- `requests>=2.31.0`: Synchronous HTTP API calls.
- `pytest>=7.4.0`: Test execution framework.
- `playwright>=1.40.0`: Headless Chromium browser automation for automated authentication.

### Standard & Utility Libraries Used
- `sqlite3`, `ctypes`, `base64`, `shutil`, `tempfile`, `json`, `re`, `datetime`, `logging`, `subprocess`.
- Optional: `cryptography.hazmat.primitives.ciphers.aead.AESGCM` (for local Windows Chrome/Edge DPAPI cookie decryption fallback).

### Environment Variables (`.env.example`)
- `TELEGRAM_TOKEN`: Telegram Bot API token.
- `TELEGRAM_CHAT_ID`: Destination Telegram chat/channel ID.
- `COLSUBSIDIO_USER`: Login username / ID document number.
- `COLSUBSIDIO_PASS`: Account password.
- `COLSUBSIDIO_SISTEMA_COOKIE`: Current session cookie `sistema`.
- `COLSUBSIDIO_CSRF_TOKEN`: Current session token `Csrf-Token`.
- `COLSUBSIDIO_DOCUMENT_TYPE`: Document type (default `CC`).
- `COLSUBSIDIO_DOCUMENT_NUMBER`: Document number (default `1002559691`).
- *Legacy (to remove)*: `COLSUBSIDIO_TIQUETERA_ID`.

---

## 5. Tests & Test Suite Mapping

- **Framework**: `pytest` running against `harness/tests/`.
- **Test File Inventory**:
  1. `test_scraper.py`: Tests API endpoint response parsing, HTTP 401 detection, automatic session recovery, and (legacy) `book_slot()`.
  2. `test_notifier.py`: Tests Telegram message sending, Markdown formatting, and slot compilation de-duplication cache.
  3. `test_orchestrator.py`: Tests schedule window filtering (`is_within_preferred_schedule`), Colombian holiday calculation, and slot diff calculation (`find_new_slots`).
  4. `test_get_cookies.py`: Tests Playwright browser initialization, form filling, cookie extraction, and `.env` file updating.
  5. `test_m2_adversarial.py`: Stress tests missing credentials, malformed `.env` files, and missing Playwright binaries.
  6. `test_m3_adversarial_challenger.py` & `test_m3_challenger_session.py`: Stress tests persistent 401 errors, malformed JSON responses, network failures during login renewal, and thread concurrency.
  7. `test_m4_cicd_local_runner.py`: Validates `requirements.txt`, `.env.example`, `check.yml` workflow syntax, and batch runner scripts.

---

## 6. CI/CD Workflows (`.github/workflows/check.yml`)

Current Setup:
- **Trigger**: Cron job `*/10 * * * *` (every 10 minutes), plus `workflow_dispatch` (with `force` boolean option) and `repository_dispatch`.
- **Runner**: `ubuntu-latest` with Python 3.11 (`actions/setup-python@v5`).
- **Dependencies**: Installs `code/requirements.txt`, caches `~/.cache/ms-playwright`, runs `python -m playwright install --with-deps chromium`.
- **State Persistence**: Uses `actions/cache` for `.cooldown_state` and `.last_slots.json`.
- **Execution**: `python code/main.py --once`.

Required Adjustments for 2026-08-12 Specs:
1. Update cron schedule from `*/10 * * * *` to `*/20 * * * *` (every 20 minutes).
2. Remove `COLSUBSIDIO_TIQUETERA_ID` from the step environment block.

---

## 7. Legacy Code Identification & Removal Inventory

To achieve the simplified read-only availability monitoring scope requested in the 2026-08-12 update, the following legacy components must be removed:

| File | Target Lines / Section | Description / Rationale |
|---|---|---|
| `code/config.py` | Lines 32–33 (`COLSUBSIDIO_TIQUETERA_ID`) | Legacy tiquetera ID environment variable. |
| `code/scraper.py` | Lines 245–345 (`book_slot()` method) | Legacy reservation execution logic calling `/v1/.../reservar`. |
| `code/main.py` | Lines 233–280 (interactive `/agendar` command processing) | Telegram command listening for booking slots using tiqueteras. |
| `code/notifier.py` | Line 187 (`/agendar` link generation in `notify_venue_slots()`) | Command link inclusion in notification text. |
| `.github/workflows/check.yml` | Line 67 (`COLSUBSIDIO_TIQUETERA_ID`) | Secret mapping in workflow execution step. |
| `harness/tests/test_scraper.py` | Lines 128–162, 248–283 (`test_book_slot_*`) | Test cases covering reservation functionality. |
| `harness/tests/test_notifier.py` | Lines 114–142 (`test_get_incoming_commands_*`) | Test cases covering `/agendar` command fetching. |

---

## 8. Current API Scraper Implementation & Business Logic Gaps

### API Endpoints
1. **Calendar Endpoint**: `POST https://www.diversioncolsubsidio.com/v1/centro_entrenamiento/{service_id}/practicalibre/calendario`
   - **Payload**:
     ```json
     {
       "filtro_disponibilidad": {
         "fecha_inicio": "YYYY-MM-DD",
         "fecha_fin": "YYYY-MM-DD",
         "inicio_inmediato": false
       }
     }
     ```
   - **Response**: Map of dates with `disponibilidad: true/false`.

2. **Availability Endpoint**: `POST https://www.diversioncolsubsidio.com/v1/centro_entrenamiento/{service_id}/practicalibre/disponibilidad?filtrarSinCupo=0`
   - **Payload**:
     ```json
     {
       "filtro_disponibilidad": {
         "fecha_inicio": "YYYY-MM-DDT00:00:00-05:00",
         "fecha_fin": "YYYY-MM-DDT23:59:59-05:00",
         "inicio_inmediato": false,
         "categorias_precios": ["A", "B", "C", "D", "INVITADO"]
       },
       "turno_practica_libre": {
         "cantidad_usos": 1,
         "numero_participantes": 1,
         "persona": [{"tipo_documento": "CC", "documento": "...", "datos": {}}]
       }
     }
     ```
   - **Response**: `horarios` array with `hora_inicio`, `cupos`, and `zonas`.

### Business Logic Gaps (Current vs. 2026-08-12 Requirements)

1. **Schedule Preference Filter**:
   - *Current Implementation (`main.py` lines 158–177)*:
     - Weekdays (Mon–Fri non-holidays): Start time between 18:00 (6 PM) and 20:00 (8 PM).
   - *2026-08-12 Requirement R2*:
     - Weekdays (Mon–Fri non-holidays): Start time **before 7:00 AM (`< 07:00`) OR after 5:00 PM (`>= 17:00`)**.
     - Weekends (Sat–Sun) & Colombian Holidays: Any time of day (24h).

2. **Telegram Message Formatting**:
   - *Current Implementation (`notifier.py` lines 165–193)*:
     - Includes `/agendar_ID_YYYY_MM_DD_HH_MM` action links on each line.
   - *2026-08-12 Requirement R3*:
     - Simple, clean, structured message format: Date, Time, Venue/Pool, Free Slots (without interactive reservation commands).

3. **Cron Job Frequency**:
   - *Current Implementation (`.github/workflows/check.yml` line 6)*: `*/10 * * * *` (10 minutes).
   - *2026-08-12 Requirement R4*: `*/20 * * * *` (20 minutes).

---

## 9. Recommendations & Next Steps

1. **Phase 1 (Legacy Code Purge)**:
   - Remove `book_slot()` from `code/scraper.py`.
   - Remove interactive command handlers from `code/main.py` and `code/notifier.py`.
   - Remove `COLSUBSIDIO_TIQUETERA_ID` references from `code/config.py` and `.github/workflows/check.yml`.

2. **Phase 2 (Filter Engine Refactoring)**:
   - Update `is_within_preferred_schedule()` in `code/main.py` to match the `< 07:00` or `>= 17:00` weekday filter rule.
   - Clean up Telegram message templates in `code/notifier.py` to produce clean summary notifications.

3. **Phase 3 (CI/CD Update)**:
   - Update `.github/workflows/check.yml` cron schedule to `*/20 * * * *`.

4. **Phase 4 (Test Suite Updating)**:
   - Update `harness/tests/test_orchestrator.py` and `harness/tests/test_notifier.py` to reflect updated schedule windows and notification formats.
