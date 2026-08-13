# Specification Mining Report — Colsubsidio Swimming Availability Monitor

- **Agent**: `teamwork_preview_spec_miner`
- **Working Directory**: `j:\Mi unidad\Natacion Colsubsidio\.agents\spec_miner_survey_1`
- **Specification Source**: `ORIGINAL_REQUEST.md`, `PROJECT.md`, `code/*`, `.github/workflows/check.yml`
- **Date**: 2026-08-11

---

## Executive Summary

This report documents the extracted specifications for the **Colsubsidio Swimming Availability Monitor** (`Natacion Colsubsidio`). Per the updated scope requirement (dated 2026-08-12 in `ORIGINAL_REQUEST.md`), the system has been refactored to focus exclusively on monitoring available swimming slots, enforcing strict schedule preferences, delivering clean Telegram notifications without duplicate alerts, running via GitHub Actions Cron (every 20 minutes), and completely removing all reservation and tiquetera consumption code.

---

## Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Documentation | `DEVTOOLS_COOKIE_GUIDE` | Step-by-step documentation in `README.md` for manual cookie retrieval and renewal using browser DevTools (Chrome, Edge, Firefox). | User browser session on `diversioncolsubsidio.com` | `COLSUBSIDIO_SISTEMA_COOKIE` and `COLSUBSIDIO_CSRF_TOKEN` strings | N/A (Manual procedure documented with troubleshoot section) | `ORIGINAL_REQUEST.md` (AC2), DISPATCH.md |
| 2 | Configuration | `ENVIRONMENT_SECRET_CONFIG` | Local `.env` and GitHub Actions secrets specification for authenticated read-only API access. | Environment variables / GitHub Secrets | Loaded configuration constants in `code/config.py` | Missing secrets log warning; invalid cookies trigger HTTP 401 handle | `ORIGINAL_REQUEST.md` (R4, AC1), `code/config.py`, `.env.example` |
| 3 | Automation | `GITHUB_ACTIONS_CRON` | CI/CD automation running every 20 minutes via GitHub Actions cron, with state caching. | Schedule `*/20 * * * *`, `workflow_dispatch` (force param), `repository_dispatch` | Automated execution of `code/main.py --once` | Job fails cleanly or reports session expiration without crashing runner | `ORIGINAL_REQUEST.md` (R4, AC1), `.github/workflows/check.yml` |
| 4 | Business Logic | `STRICT_SCHEDULE_FILTER` | Filter engine restricting slot notifications to user preferred windows (Weekdays < 7am or >= 5pm; Weekends & Colombian Holidays 24h). | Raw slots list from API (`date_str`, `time_str`) | Filtered slots matching schedule preferences | Invalid date format returns `False` and logs error | `ORIGINAL_REQUEST.md` (R2, AC1), `code/main.py` |
| 5 | Notifications | `CLEAN_TELEGRAM_NOTIFICATIONS` | Markdown Telegram messages reporting available slots grouped by venue and date, without reservation links. | Sede name, filtered slots list, `force` boolean flag | Markdown message posted to Telegram Chat API | Connection errors logged without crashing loop; HTTP errors logged | `ORIGINAL_REQUEST.md` (R3, AC1), `code/notifier.py` |
| 6 | State & Cache | `DEDUPLICATION_CACHE_ENGINE` | State persistence in `.last_slots.json` and `.cooldown_state` preventing repeated alerts for identical slot availability. | Current run slots dict vs stored `.last_slots.json` | Updated state files; suppressed duplicate Telegram messages | File read/write errors logged gracefully; falls back to empty cache | `ORIGINAL_REQUEST.md` (R3), `code/main.py`, `.github/workflows/check.yml` |
| 7 | Code Cleanup | `RESERVATION_LOGIC_REMOVAL` | Complete elimination of reservation methods (`book_slot`), tiquetera ID management, and interactive `/agendar` commands. | N/A (Code removal directive) | Simplified, lightweight scraper and runner | N/A | `ORIGINAL_REQUEST.md` (R1, AC1), DISPATCH.md |

---

## Detailed Specification Requirements

### 1. README Documentation — Browser DevTools Cookie Retrieval Guide (`DEVTOOLS_COOKIE_GUIDE`)

The `README.md` file MUST contain a clear, step-by-step section explaining how to extract and renew Colsubsidio session cookies manually from any modern browser.

#### Required Guide Steps:
1. **Access Portal**: Open Google Chrome, Microsoft Edge, or Mozilla Firefox and navigate to:
   `https://www.diversioncolsubsidio.com/deportes-practica-libre-natacion#/wizard?producto=80`
2. **Authenticate**: Log in to your Colsubsidio account if prompted.
3. **Open Developer Tools**: Press `F12` (or `Ctrl + Shift + I` on Windows / `Cmd + Option + I` on macOS).
4. **Locate Cookies**:
   - **Chrome / Edge**: Select **Application** tab -> expand **Storage** -> **Cookies** -> click `https://www.diversioncolsubsidio.com`.
   - **Firefox**: Select **Storage** tab -> expand **Cookies** -> click `https://www.diversioncolsubsidio.com`.
   - **Alternative (Network Tab)**: Select **Network** tab, perform any query on the page, select a request to `v1/centro_entrenamiento/...`, and look under **Request Headers**.
5. **Copy Secret Values**:
   - Cookie `sistema`: Copy the entire text string value -> `COLSUBSIDIO_SISTEMA_COOKIE`.
   - Cookie `Csrf-Token`: Copy the entire text string value -> `COLSUBSIDIO_CSRF_TOKEN`.
6. **Apply to Environment**:
   - **Local Run**: Update `.env`:
     ```env
     COLSUBSIDIO_SISTEMA_COOKIE=your_extracted_sistema_cookie
     COLSUBSIDIO_CSRF_TOKEN=your_extracted_csrf_token
     ```
   - **GitHub Actions**: Navigate to GitHub Repository -> **Settings** -> **Secrets and variables** -> **Actions** -> Add or update repository secrets `COLSUBSIDIO_SISTEMA_COOKIE` and `COLSUBSIDIO_CSRF_TOKEN`.

---

### 2. Environment Variables & Secret Configurations (`ENVIRONMENT_SECRET_CONFIG`)

#### Required Configuration Variables:

| Variable / Secret Name | Required In | Purpose | Example / Format |
|------------------------|-------------|---------|------------------|
| `TELEGRAM_TOKEN` | `.env` & GitHub Secrets | Telegram Bot API token | `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ` |
| `TELEGRAM_CHAT_ID` | `.env` & GitHub Secrets | Target Telegram chat ID for alerts | `987654321` or `-100123456789` |
| `COLSUBSIDIO_SISTEMA_COOKIE` | `.env` & GitHub Secrets | PHP session cookie for Colsubsidio portal | String (long alphanumeric hash) |
| `COLSUBSIDIO_CSRF_TOKEN` | `.env` & GitHub Secrets | Anti-CSRF token cookie/header | String (UUID / alphanumeric hash) |

#### Removed / Deprecated Variables:
- `COLSUBSIDIO_USER`: No longer needed (Playwright automatic login removed).
- `COLSUBSIDIO_PASS`: No longer needed (Playwright automatic login removed).
- `COLSUBSIDIO_DOCUMENT_TYPE`: Deprecated (not required for availability queries).
- `COLSUBSIDIO_DOCUMENT_NUMBER`: Deprecated (not required for availability queries).
- `COLSUBSIDIO_TIQUETERA_ID`: Removed (reservation & tiquetera logic removed).

#### GitHub Actions Workflow Specification (`.github/workflows/check.yml`):
- **Cron Schedule**: `cron: '*/20 * * * *'` (runs every 20 minutes).
- **Manual Trigger**: `workflow_dispatch` with optional boolean parameter `force` (forces full report delivery regardless of slot delta).
- **Dispatch Trigger**: `repository_dispatch` (types: `[check]`).
- **Dependencies**: Only installs standard Python packages from `code/requirements.txt` (Playwright installation steps removed).
- **Secrets passed to environment**:
  ```yaml
  env:
    TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
    TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
    COLSUBSIDIO_SISTEMA_COOKIE: ${{ secrets.COLSUBSIDIO_SISTEMA_COOKIE }}
    COLSUBSIDIO_CSRF_TOKEN: ${{ secrets.COLSUBSIDIO_CSRF_TOKEN }}
  ```
- **State Caching**: Preserves `.cooldown_state` and `.last_slots.json` across workflow runs via `actions/cache@v4`.

---

### 3. Exact Message Formatting & Deduplication (`CLEAN_TELEGRAM_NOTIFICATIONS`)

#### Strict Schedule Filter Engine Rules:
- **Weekdays (Lunes a Viernes, non-holidays)**:
  - Turnos starting **before 7:00 AM** (`hora < "07:00"` / `hour < 7`).
  - Turnos starting **after or at 5:00 PM** (`hora >= "17:00"` / `hour >= 17`).
  - Turnos between 07:00 AM and 04:59 PM are filtered out.
- **Weekends (Sábados y Domingos) & Colombian Holidays**:
  - All hours allowed (`00:00` to `23:59` / 24 hours).
- **Colombian Holiday Engine**: Evaluates official holidays dynamically via Emiliani law calculation.

#### Telegram Message Formatting Specification:
Messages MUST be simple, clean, short, and structured using Telegram Markdown. They MUST NOT contain interactive `/agendar_...` commands.

```markdown
🏊 *¡Cupos Libres de Natación!*

📍 *Sede:* EL CUBO

📅 *Lunes 2026-08-17:*
• ⏰ `06:00` — 🎟️ `3` cupos libres
• ⏰ `17:00` — 🎟️ `1` cupos libres
• ⏰ `18:00` — 🎟️ `5` cupos libres

📅 *Martes 2026-08-18:*
• ⏰ `06:30` — 🎟️ `2` cupos libres
```

#### Deduplication & Cache Rules:
- Keys stored in `.last_slots.json` format: `{"EL CUBO": [{"fecha": "2026-08-17", "hora": "06:00", "cupos": 3}, ...]}`.
- Alert key in memory / cache: `venue:fecha:hora:cupos`.
- A notification is sent ONLY IF:
  1. A new slot appears that was not in `.last_slots.json`, OR
  2. An existing slot's available count (`cupos`) increases, OR
  3. `--force` (or `github.event.inputs.force == 'true'`) is specified.

---

### 4. Reservation Code Removal Criteria (`RESERVATION_LOGIC_REMOVAL`)

To simplify the codebase and align with the read-only monitoring scope, the following code structures MUST be completely removed:

| Source File | Entity / Block to Remove | Rationale |
|-------------|--------------------------|-----------|
| `code/scraper.py` | `book_slot()` method (lines 245–345) | Reservation logic eliminated. |
| `code/scraper.py` | `_renew_session()` Playwright integration | Automated Playwright login eliminated in favor of manual DevTools cookie entry. |
| `code/main.py` | Interactive Telegram command processing loop in `main()` (lines 229–280) | `/agendar_...` command handling removed. |
| `code/notifier.py` | `get_incoming_commands()` method (lines 75–104) | Bot polling for incoming commands removed. |
| `code/notifier.py` | `/agendar_...` command link construction in `notify_venue_slots()` | Messages should contain only slot details, no booking links. |
| `code/config.py` | `COLSUBSIDIO_TIQUETERA_ID` definition | Tiquetera management removed. |
| `code/get_cookies.py` | Playwright browser automation module | Playwright dependencies removed. |
| `code/requirements.txt` | `playwright` package line | Unused dependency removed. |
| `.github/workflows/check.yml` | Playwright browser caching & installation steps; unused secrets | Workflow streamlined for fast, lightweight execution. |

---

## Edge Cases

| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | `ENVIRONMENT_SECRET_CONFIG` | Expired `COLSUBSIDIO_SISTEMA_COOKIE` | API returns HTTP 401. Scraper raises `SessionExpiredException`. `main.py` catches it, sends a Telegram session expiration alert (throttled to 1 per 24h), and exits cleanly (exit code 0). |
| 2 | `STRICT_SCHEDULE_FILTER` | Slot at `07:00` on a Tuesday (weekday) | Filter excludes slot because weekday morning window is strictly `< 07:00` (starts before 7:00 AM). |
| 3 | `STRICT_SCHEDULE_FILTER` | Slot at `17:00` on a Wednesday (weekday) | Filter includes slot because weekday evening window starts at `17:00` (5:00 PM). |
| 4 | `STRICT_SCHEDULE_FILTER` | Slot at `10:00` AM on a Monday that is a Colombian Holiday (e.g. May 1) | `is_colombian_holiday()` returns `True`. Filter treats day as weekend, allowing the 10:00 AM slot. |
| 5 | `DEDUPLICATION_CACHE_ENGINE` | Consecutive run with zero changes in slot availability | `find_new_slots()` returns empty list. Notification omitted to prevent Telegram spam. |
| 6 | `DEDUPLICATION_CACHE_ENGINE` | Slot count increases from 1 to 3 for same fecha/hora | `find_new_slots()` detects `cupos > last_cupos`. New alert notification triggered. |
| 7 | `GITHUB_ACTIONS_CRON` | Manual trigger with `force: true` | `main.py --once --force` executes. `check_venues` sends complete availability report regardless of cache delta. |
| 8 | `RESERVATION_LOGIC_REMOVAL` | Incoming `/agendar_...` command sent to Telegram bot | Ignored completely (command listener loop removed). |
