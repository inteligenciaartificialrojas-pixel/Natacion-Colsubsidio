# Detailed Architecture & Self-Healing Analysis — Milestone 1 (Explorer 2)

**Workspace**: `i:\Mi unidad\Natacion Colsubsidio`  
**Working Directory**: `i:\Mi unidad\Natacion Colsubsidio\.agents\explorer_m1_2`  
**Date**: 2026-08-09  

---

## 1. Executive Summary

This document provides a comprehensive technical investigation of the **Colsubsidio Swimming Availability Self-Healing Workflow** codebase, focusing on request dispatching, session expiration detection, business logic preservation, and the proposed design for the scraper-level self-healing retry mechanism.

Currently, session expiration (`SessionExpiredException`) causes `scraper.py` to immediately abort HTTP requests. Handling is pushed up to `main.py`, which attempts a local Windows browser extraction fallback (`get_cookies.py`). Milestone 2/3 will introduce automated Playwright login renewal via `get_cookies.login_and_get_cookies()` and integrate seamless request-level retries directly inside `scraper.py`.

All 24 existing unit tests in `harness/tests` were verified and pass (`pytest harness/tests`).

---

## 2. Codebase & Component Analysis

### 2.1 `code/scraper.py` (Core Scraping Engine)
- **Session Setup**: Instantiates `requests.Session()`. Sets domain-specific cookies (`sistema`, `sitio`, `Csrf-Token`) on `www.diversioncolsubsidio.com` and `.diversioncolsubsidio.com`.
- **Default Headers**:
  - `User-Agent`: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...`
  - `Accept`: `application/json`
  - `Content-Type`: `application/json`
  - `Referer`: `https://www.diversioncolsubsidio.com/deportes-practica-libre-natacion`
- **Dispatched API Endpoints**:
  1. `fetch_available_dates(service_id: int) -> list[str]`:
     - Endpoint: `POST https://www.diversioncolsubsidio.com/v1/centro_entrenamiento/{service_id}/practicalibre/calendario`
     - Payload: `{"filtro_disponibilidad": {"fecha_inicio": today_str, "fecha_fin": future_str, "inicio_inmediato": False}}`
     - Returns sorted list of ISO date strings `['YYYY-MM-DD', ...]`.
  2. `fetch_slots_for_date(service_id: int, date_str: str) -> list[dict]`:
     - Endpoint: `POST https://www.diversioncolsubsidio.com/v1/centro_entrenamiento/{service_id}/practicalibre/disponibilidad?filtrarSinCupo=0`
     - Payload: `filtro_disponibilidad` (date range with `-05:00` offset, `categorias_precios`: `["A", "B", "C", "D", "INVITADO"]`), `turno_practica_libre` (`cantidad_usos`: 1, `numero_participantes`: 1, `persona` with user document).
     - Calculates slot capacity by summing lane capacities across `zonas`.
  3. `book_slot(service_id: int, date_str: str, time_str: str, tiquetera_id: int) -> tuple[bool, str]`:
     - Endpoint: `POST https://www.diversioncolsubsidio.com/v1/centro_entrenamiento/{service_id}/practicalibre/reservar`
     - Payload: `servicio`, `turnos_practica_libre` with selected zone ID and tiquetera ID.

### 2.2 Session Expiration Identification (`_check_unauthorized`)
`ColsubsidioScraper._check_unauthorized(response: requests.Response)` evaluates every HTTP response against 3 criteria:
1. **HTTP 401 Status**: `response.status_code == 401` -> Raises `SessionExpiredException("La API retornó HTTP 401 Unauthorized.")`.
2. **JSON Unauthorized Status**: If `Content-Type` contains `application/json` and `data.get("status") == "Unauthorized"` -> Raises `SessionExpiredException("Sesión no autorizada en el JSON de respuesta.")`.
3. **HTML Login Page / Redirect**: If `Content-Type` is not JSON and response text contains `"loguearSitio"` or `"error-no-encontrado"` -> Raises `SessionExpiredException("La sesión expiró (redirección a login o página no encontrada).")`.

Currently, `SessionExpiredException` is caught in `fetch_available_dates`, `fetch_slots_for_date`, and `book_slot` with `except SessionExpiredException: raise`, forcing the outer orchestrator to handle failure.

### 2.3 `code/main.py` (Orchestrator & Business Logic)
- Manages command execution (`--once`, continuous loop with `time.sleep(interval)`).
- Executes `check_venues()` across all configured venues (`VENUE_SERVICE_IDS`).
- Catches `SessionExpiredException` at the top level and attempts local Windows cookie extraction via `get_cookies.extract_colsubsidio_cookies()`.
- Sends daily Telegram alerts if session renewal fails (throttled to once per 24 hours).

### 2.4 `code/notifier.py` (Telegram Alerts & Interactivity)
- `TelegramNotifier` handles all Telegram API calls via `https://api.telegram.org/bot<token>/`.
- Sends consolidated Markdown messages per venue (`notify_venue_slots`).
- Formats interactive inline commands: `/agendar_<service_id>_<YYYY_MM_DD>_<HH_MM>`.
- Internal cache `_sent_alerts` de-duplicates identical availability reports within `ALERT_CACHE_DURATION_SECONDS` (1 hour default), bypassed when `force=True`.

### 2.5 `code/config.py` (Environment & Constants)
- Loads `.env` file from project root.
- Defines service IDs: `EL CUBO`: `232`, `PLAZA DE LAS AMERICAS`: `428`, `CLUB LA COLINA`: `229`.
- Defines default check interval (`DEFAULT_CHECK_INTERVAL_SECONDS = 300`).

---

## 3. Business Logic Preservation Specification

To ensure no regressions, the self-healing integration must preserve 100% of existing business rules:

| Domain | Business Rule | Implementation Location | Preservation Requirement |
|---|---|---|---|
| **Venue Filtering** | Preferred venues: El Cubo (232), Plaza de las Américas (428), Club La Colina (229). | `config.VENUE_SERVICE_IDS` | Retain exact mapping and iteration in `check_venues()`. |
| **Schedule Rules** | Weekends (Sat/Sun) & Colombian Holidays: Any time slot valid.<br>Weekdays (Mon-Fri non-holiday): Valid only if start hour is 18:00–20:00. | `main.is_within_preferred_schedule()` & `main.is_colombian_holiday()` | Must not alter holiday calendar logic (Meeus/Jones/Butcher algorithm + Ley Emiliani shifts). |
| **Telegram Notifications** | Markdown formatted venue updates with interactive `/agendar` commands. | `notifier.TelegramNotifier` | Maintain exact message layout and command structure. |
| **De-duplication Cache** | Avoid duplicate Telegram alerts within 1 hour unless new slots/increased cupos appear or `force_send=True`. | `notifier._sent_alerts` & `main.find_new_slots()` | Preserve slot delta calculation and cache key structure (`VENUE\|fecha:hora:cupos...`). |
| **State Persistence** | `.cooldown_state` tracks alert cooldown & scheduled report state.<br>`.last_slots.json` tracks last seen slots. | `main.load_cooldown_state()`, `save_cooldown_state()`, `load_last_slots()`, `save_last_slots()` | Keep JSON structure, atomic file read/write, and state keys intact. |
| **Interactive Booking** | `/agendar_ID_YYYY_MM_DD_HH_MM` command processing via Telegram `getUpdates`. | `main.main()` command parsing + `scraper.book_slot()` | Retain booking workflow, tiquetera ID validation, and status reporting. |

---

## 4. Self-Healing Retry Mechanism Design for `scraper.py`

### 4.1 Objective
Move session recovery responsibility into `ColsubsidioScraper` so that any expired session encountered during scraping or booking triggers an automatic Playwright renewal, updates session state in memory and `.env`, and retries the HTTP request seamlessly without throwing `SessionExpiredException` to caller code.

### 4.2 Module Contract & Interface Integration
- `get_cookies.login_and_get_cookies(user=None, password=None) -> dict[str, str]`:
  Automated Playwright login helper (Milestone 2) returning `{"sistema": "...", "Csrf-Token": "..."}`.
- `get_cookies.update_env_file(cookies: dict[str, str]) -> bool`:
  Persists fresh cookies into `.env` file on disk.

### 4.3 Scraper In-Memory Renewal Logic (`_renew_session`)
Within `ColsubsidioScraper`:
```python
def _renew_session(self) -> bool:
    """
    Triggers session renewal via get_cookies module (Playwright or browser extraction),
    updates in-memory session cookies, headers, and persists fresh tokens to .env.
    Returns True if renewal succeeded, False otherwise.
    """
    logger.info("Session expired or invalid. Triggering self-healing session renewal...")
    try:
        from get_cookies import login_and_get_cookies, update_env_file
        
        cookies = login_and_get_cookies()
        if cookies and "sistema" in cookies:
            sistema_val = cookies["sistema"]
            csrf_val = cookies.get("Csrf-Token", "")

            # Update requests.Session in-memory cookies
            self.session.cookies.set("sistema", sistema_val, domain="www.diversioncolsubsidio.com")
            self.session.cookies.set("sistema", sistema_val, domain=".diversioncolsubsidio.com")
            self.session.cookies.set("sitio", sistema_val, domain="www.diversioncolsubsidio.com")
            self.session.cookies.set("sitio", sistema_val, domain=".diversioncolsubsidio.com")
            if csrf_val:
                self.session.cookies.set("Csrf-Token", csrf_val, domain="www.diversioncolsubsidio.com")
                self.session.cookies.set("Csrf-Token", csrf_val, domain=".diversioncolsubsidio.com")

            # Persist to .env and environment variables
            update_env_file(cookies)
            os.environ["COLSUBSIDIO_SISTEMA_COOKIE"] = sistema_val
            if csrf_val:
                os.environ["COLSUBSIDIO_CSRF_TOKEN"] = csrf_val

            logger.info("Session refreshed successfully. In-memory session and .env updated.")
            return True
        else:
            logger.error("Session renewal returned invalid cookie dict.")
            return False
    except Exception as e:
        logger.error("Error during session renewal: %s", e)
        return False
```

### 4.4 Seamless Request Retry Pattern (`_execute_with_retry`)
To avoid code duplication across `fetch_available_dates`, `fetch_slots_for_date`, and `book_slot`, a helper method `_execute_with_retry` will wrap HTTP requests:

```python
def _execute_with_retry(self, request_func, max_retries: int = 1):
    """
    Executes request_func(). If SessionExpiredException is raised, calls _renew_session()
    and retries request_func() up to max_retries times.
    """
    for attempt in range(max_retries + 1):
        try:
            return request_func()
        except SessionExpiredException as e:
            if attempt < max_retries:
                logger.warning("Session expired on attempt %d. Attempting auto-healing retry...", attempt + 1)
                if self._renew_session():
                    continue
            raise e
```

### 4.5 Flow Sequence Diagram (Conceptual)

```
Caller (main.py)           Scraper.fetch_slots()          Colsubsidio API          get_cookies.login_and_get_cookies()
    |                             |                              |                                     |
    |---- fetch_slots_for_date--->|                              |                                     |
    |                             |--- POST /disponibilidad ---->|                                     |
    |                             |<-- HTTP 401 / Login HTML ----|                                     |
    |                             |                              |                                     |
    |                             |-- SessionExpiredException -- |                                     |
    |                             |                              |                                     |
    |                             |--- Trigger _renew_session() -------------------------------------->|
    |                             |                                                                    | [Playwright Headless Login]
    |                             |<-- dict{"sistema": "...", "Csrf-Token": "..."} -------------------|
    |                             |                                                                    |
    |                             |-- Update in-memory session & .env                                  |
    |                             |                              |                                     |
    |                             |--- POST /disponibilidad ---->| (with fresh cookies)                |
    |                             |<-- HTTP 200 JSON ------------|                                     |
    |                             |                              |                                     |
    |<--- Return slots list ------|                              |                                     |
```

### 4.6 Verification & Safety Guarantees
1. **Single Renewal Attempt per Request**: `max_retries = 1` prevents infinite renewal loops if credentials are fundamentally invalid.
2. **Atomic In-Memory + Disk Sync**: Updating both `self.session.cookies` and `.env` guarantees both immediate request continuation and persistence across script restarts.
3. **Escalation**: If renewal fails, `SessionExpiredException` propagates to `main.py`, which triggers the 24-hour rate-limited Telegram alert.

---

## 5. Conclusion & Next Steps

The proposed self-healing design in `scraper.py` cleanly separates session renewal, retry execution, and business logic. Milestone 2 will implement `login_and_get_cookies` using Playwright Chromium in `code/get_cookies.py`, and Milestone 3 will integrate this self-healing retry mechanism into `code/scraper.py`.
