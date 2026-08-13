# Project: Colsubsidio Swimming Availability Monitor

## Architecture
- **Language**: Python 3.11+
- **Core Modules (`code/`)**:
  - `config.py`: Environment configuration, venue IDs, schedule windows.
  - `scraper.py`: Colsubsidio API availability endpoints client (`calendario`, `disponibilidad`) with session cookie authentication (`COLSUBSIDIO_SISTEMA_COOKIE`, `COLSUBSIDIO_CSRF_TOKEN`) and 401 handling.
  - `main.py`: CLI orchestration loop, schedule window filter engine (`is_within_preferred_schedule`), Colombian holiday rules (`is_colombian_holiday`), slot state deduplication (`.last_slots.json`, `.cooldown_state`).
  - `notifier.py`: Clean Telegram message formatting and delivery (`notify_venue_slots`).
  - `get_cookies.py`: Browser devtools / Playwright cookie extraction helper script.
- **CI/CD (`.github/workflows/check.yml`)**: GitHub Actions workflow running on 20-minute cron (`*/20 * * * *`) and `workflow_dispatch`.
- **Test Suite (`harness/tests/`)**: Pytest test suite covering unit tests, integration tests, adversarial stress tests, and CI/CD validation.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Cookie Session Scraper Refactoring | Query availability endpoints (`/v1/centro_entrenamiento/{id}/practicalibre/calendario` and `disponibilidad`) using `COLSUBSIDIO_SISTEMA_COOKIE` and `COLSUBSIDIO_CSRF_TOKEN` headers, with 401 session expiration handling | M1 | ORIGINAL_REQUEST § R1 |
| F2 | Legacy Reservation Code Removal | Remove `book_slot()`, `/agendar` Telegram command parser, `COLSUBSIDIO_TIQUETERA_ID`, and associated tests/secrets | M1 | ORIGINAL_REQUEST § R1 & Acceptance Criteria |
| F3 | Strict Schedule Filter Engine | Filter free slots: Mon-Fri < 07:00 or >= 17:00 (17:00-23:59), Sat-Sun & Colombian Holidays 24h | M2 | ORIGINAL_REQUEST § R2 |
| F4 | Clean Telegram Notifications & Deduplication | Short structured Telegram messages (Date, Time, Venue, Free Slots), removing booking links; maintain state cache `.last_slots.json` / `.cooldown_state` | M2 | ORIGINAL_REQUEST § R3 |
| F5 | GitHub Actions CI/CD Automation | Configure `.github/workflows/check.yml` to run every 20 minutes (`*/20 * * * *`) and via `workflow_dispatch`, using secrets (`TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `COLSUBSIDIO_SISTEMA_COOKIE`, `COLSUBSIDIO_CSRF_TOKEN`) | M3 | ORIGINAL_REQUEST § R4 |
| F6 | Browser DevTools Cookie Renewal Guide | Step-by-step README documentation for obtaining and renewing session cookies via DevTools in Chrome, Edge, and Firefox | M3 | ORIGINAL_REQUEST § Acceptance Criteria & Docs |
| F7 | Final E2E Test Suite Pass & Coverage Hardening | Pass 100% of E2E tests (Tiers 1-4) and complete Tier 5 white-box adversarial coverage hardening | M4 | Project Pattern Dual Track |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M-TEST | E2E Testing Suite Track | Requirement-driven opaque-box E2E test suite (Tiers 1-4) covering F1-F6 | none | DONE |
| M1 | Scraper Refactoring & Legacy Removal | Refactor scraper for availability endpoints & cookies; purge legacy reservation/tiquetera logic (F1, F2) | none | DONE |
| M2 | Filter Engine & Telegram Deduplication | Refactor schedule filter (<07:00 / >=17:00 weekdays, 24h weekends/holidays); clean Telegram alerts & cache state (F3, F4) | M1 | IN_PROGRESS |
| M3 | CI/CD Cron Automation & DevTools Docs | Update `.github/workflows/check.yml` to 20-min cron & clean secrets; write README DevTools cookie guide (F5, F6) | M2 | PLANNED |
| M4 | Final E2E Test Pass & Coverage Hardening | Run 100% E2E test suite against implementation, followed by Tier 5 adversarial coverage hardening (F7) | M-TEST, M3 | PLANNED |

## Interface Contracts
### `scraper.py` ↔ `main.py`
- `ColsubsidioScraper.__init__(sistema_cookie: str, csrf_token: str)`
- `ColsubsidioScraper.fetch_available_dates(venue_id: str) -> List[str]`
- `ColsubsidioScraper.fetch_slots_for_date(venue_id: str, date_str: str) -> List[Dict]`
- Raises `SessionExpiredException` on 401 HTTP response.

### `main.py` ↔ `notifier.py`
- `is_within_preferred_schedule(dt: datetime) -> bool`
- `TelegramNotifier.notify_venue_slots(venue_name: str, slots_by_date: Dict[str, List[Dict]]) -> bool`

## Code Layout
- `code/config.py`
- `code/scraper.py`
- `code/main.py`
- `code/notifier.py`
- `code/get_cookies.py`
- `.github/workflows/check.yml`
- `README.md`
