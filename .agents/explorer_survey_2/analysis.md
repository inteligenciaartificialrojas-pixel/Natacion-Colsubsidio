# Analysis Report — Colsubsidio Swimming Availability Monitor (Survey 2)

- **Agent Identity**: `teamwork_preview_explorer`
- **Working Directory**: `j:\Mi unidad\Natacion Colsubsidio\.agents\explorer_survey_2`
- **Specification Source**: `j:\Mi unidad\Natacion Colsubsidio\.agents\ORIGINAL_REQUEST.md` (Update 2026-08-12)
- **Target Project Root**: `j:\Mi unidad\Natacion Colsubsidio`
- **Date**: 2026-08-12

---

## 1. Executive Summary & Objective Alignment

The objective of this analysis is to evaluate the existing codebase of the **Colsubsidio Swimming Availability Monitor** against the updated scope requirements specified on 2026-08-12 in `ORIGINAL_REQUEST.md`.

### Core Scope Shift
- **Previous Scope (2026-08-09)**: Full auto-healing workflow with Playwright headless Chromium login, automated cookie renewal on 401, interactive Telegram booking commands (`/agendar_...`), and slot reservation execution using user tiquetera.
- **Updated Scope (2026-08-12)**: Lightweight, read-only availability monitoring system deployed on GitHub Actions running every 20 minutes via cron. Exclusively queries available swimming slots for user-preferred schedule windows, sends clean Telegram notifications without reservation links, and maintains persistent deduplication state across executions. All reservation logic, Playwright automation, and tiquetera consumption are completely eliminated.

---

## 2. Detailed Technical Requirements & Domain Analysis

### Domain 1: Availability API Scraper & Cookie Session Handling (R1)

#### Endpoints Specification
The Colsubsidio frontend AngularJS app (`https://www.diversioncolsubsidio.com/deportes-practica-libre-natacion#/wizard?producto=80`) interacts with two core backend REST endpoints:

1. **Calendar Endpoint (`fetch_available_dates`)**:
   - **URL**: `POST https://www.diversioncolsubsidio.com/v1/centro_entrenamiento/{id}/practicalibre/calendario`
   - **Service IDs (`{id}`)**:
     - `232`: EL CUBO
     - `428`: PLAZA DE LAS AMERICAS
     - `229`: CLUB LA COLINA
   - **Request Payload**:
     ```json
     {
       "filtro_disponibilidad": {
         "fecha_inicio": "YYYY-MM-DD",
         "fecha_fin": "YYYY-MM-DD",
         "inicio_inmediato": false
       }
     }
     ```
   - **Response Structure**:
     ```json
     {
       "fechas": {
         "2026-08-15": { "fecha": "2026-08-15", "disponibilidad": true },
         "2026-08-16": { "fecha": "2026-08-16", "disponibilidad": false }
       }
     }
     ```
   - **Current Implementation**: `code/scraper.py:109-157`.

2. **Availability / Slot Details Endpoint (`fetch_slots_for_date`)**:
   - **URL**: `POST https://www.diversioncolsubsidio.com/v1/centro_entrenamiento/{id}/practicalibre/disponibilidad?filtrarSinCupo=0`
   - **Request Payload**:
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
         "persona": [
           {
             "tipo_documento": "CC",
             "documento": "1002559691",
             "datos": {}
           }
         ]
       }
     }
     ```
   - **Response Structure**:
     ```json
     {
       "horarios": [
         {
           "horario": { "hora_inicio": "06:00:00", "hora_fin": "06:50:00" },
           "cupos": 3,
           "zonas": [
             { "id": 101, "capacidad_disponible": 2 },
             { "id": 102, "capacidad_disponible": 1 }
           ]
         }
       ]
     }
     ```
   - **Current Implementation**: `code/scraper.py:158-244`.

#### Cookie Headers & Authentication Requirements
- **Required Session Cookies**:
  - `sistema`: PHP Session Token for `diversioncolsubsidio.com`.
  - `Csrf-Token`: CSRF Token set as both cookie and HTTP header `Csrf-Token`.
- **Unauthorized Session Detection (`_check_unauthorized`)**:
  - **HTTP Status**: Returns `401 Unauthorized`.
  - **JSON Body**: Response `{"status": "Unauthorized"}` with HTTP 200.
  - **HTML Redirect**: HTML response containing `"loguearSitio"` or `"error-no-encontrado"`.
- **Handling Strategy**:
  - When `SessionExpiredException` is raised during execution in CI/CD, `main.py` catches it, sends a Telegram notification instructing the user to update secrets, and exits with code 0 (throttled to 1 alert every 24 hours via `.cooldown_state`).

---

### Domain 2: Strict Schedule Filter Engine (R2)

#### Requirements vs Existing Implementation

| Rule Aspect | Existing Implementation (`code/main.py:158-177`) | New Specification (`ORIGINAL_REQUEST.md:55-58`) | Required Action |
|-------------|--------------------------------------------------|--------------------------------------------------|-----------------|
| **Mon-Fri (Weekdays)** | `18 <= hour <= 20` (6:00 PM to 8:00 PM) | Turnos **antes de 7:00 AM** (`hour < 7`) o **después de 5:00 PM** (`hour >= 17`). | Update filter condition in `is_within_preferred_schedule()`. |
| **Sat-Sun (Weekends)** | Any time (`day_of_week >= 5`) | Any time (24h). | Retain existing logic (`day_of_week >= 5`). |
| **Colombian Holidays** | Allowed 24h via `is_colombian_holiday()` | Evaluated as weekend/holiday (24h). | Retain existing `is_colombian_holiday()` engine. |

#### Updated Filter Logic Matrix:
```python
def is_within_preferred_schedule(date_str: str, time_str: str) -> bool:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_of_week = dt.weekday()  # 0 = Monday, 6 = Sunday
        
        # Sábados, Domingos y Festivos colombianos: 24 horas permitidas
        if day_of_week >= 5 or is_colombian_holiday(dt.date()):
            return True

        # Lunes a Viernes: antes de 7:00 AM (< 7) o después/igual a 5:00 PM (>= 17)
        hour = int(time_str.split(":")[0])
        return hour < 7 or hour >= 17
    except Exception as e:
        logger.error("Error al evaluar horario preferido (%s, %s): %s", date_str, time_str, e)
        return False
```

---

### Domain 3: Clean Telegram Notifications & State Deduplication (R3)

#### Notification Cleanup
- **Remove**: Interactive booking commands (`/agendar_...`), booking instructions, processing loops, and tiquetera parameters.
- **Message Format**: Clean, compact Markdown listing:

```markdown
🏊 *¡Cupos Libres de Natación!*

📍 *Sede:* EL CUBO

📅 *Lunes 2026-08-17:*
• ⏰ `06:00` — 🎟️ `3` cupos libres
• ⏰ `17:00` — 🎟️ `1` cupos libres
• ⏰ `18:00` — 🎟️ `5` cupos libres

📅 *Martes 2026-08-18:*
• ⏰ `06:30` — 🎟️ `2` cupos libres

🔗 _Consulta en la Tienda de Diversión Colsubsidio_
```

#### State Persistence & Deduplication Architecture
- **`.last_slots.json`**: Stores the last detected slot state per venue:
  ```json
  {
    "EL CUBO": [
      { "fecha": "2026-08-17", "hora": "06:00", "cupos": 3 },
      { "fecha": "2026-08-17", "hora": "18:00", "cupos": 5 }
    ]
  }
  ```
- **Delta Algorithm (`find_new_slots`)**:
  - Compares `current_slots` against `last_slots`.
  - A slot is considered **new/reportable** if:
    1. Key `(fecha, hora)` does not exist in `last_slots`.
    2. `cupos` count is strictly greater than `last_slots[(fecha, hora)]`.
- **`.cooldown_state`**: Stores run metadata:
  ```json
  {
    "last_expiry_alert_time": 1723438000.0,
    "last_report_sent": "2026-08-12-06"
  }
  ```

---

### Domain 4: GitHub Actions CI/CD Cron Automation (R4)

#### Workflow Analysis (`.github/workflows/check.yml`)

1. **Cron Schedule**:
   - Current: `cron: '*/10 * * * *'` (every 10 min).
   - Target: `cron: '*/20 * * * *'` (every 20 min).

2. **Trigger Support**:
   - `schedule`: Periodic background execution.
   - `workflow_dispatch`: Manual trigger with optional `force` boolean.
   - `repository_dispatch`: External webhook event support.

3. **Secrets Required**:
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `COLSUBSIDIO_SISTEMA_COOKIE`
   - `COLSUBSIDIO_CSRF_TOKEN`

4. **Optimization / Cleanup Opportunity**:
   - Playwright installation steps (`python -m playwright install --with-deps chromium`) and caching steps can be removed from `check.yml` to reduce workflow execution time from ~90 seconds down to ~10 seconds.

---

## 3. Scope Cleanup & Refactoring Assessment

To adhere strictly to the 2026-08-12 user specification, the following elements should be removed or simplified:

1. **`code/scraper.py`**:
   - Remove `book_slot()` method (lines 245–346).
   - Remove Playwright import and `_renew_session()` helper (lines 56–70).

2. **`code/main.py`**:
   - Remove Telegram command listening loop (`get_incoming_commands()` & `/agendar_...` handler).
   - Remove Playwright session renewal fallback inside `SessionExpiredException` catch block.
   - Update `is_within_preferred_schedule()` for `hour < 7 or hour >= 17`.

3. **`code/notifier.py`**:
   - Remove `get_incoming_commands()` method.
   - Remove `/agendar_...` link generation in `notify_venue_slots()`.

4. **`code/config.py`**:
   - Remove `COLSUBSIDIO_TIQUETERA_ID` and credentials `COLSUBSIDIO_USER`, `COLSUBSIDIO_PASS`.

5. **`code/requirements.txt`**:
   - Remove `playwright` dependency.

---

## 4. Summary of Code Changes Required

| Component | Target File | Action | Key Details |
|-----------|-------------|--------|-------------|
| Config | `code/config.py` | Update | Remove `COLSUBSIDIO_TIQUETERA_ID`, `USER`/`PASS`. |
| Filter Engine | `code/main.py` | Edit `is_within_preferred_schedule` | Set weekday logic: `hour < 7 or hour >= 17`. |
| Orchestration | `code/main.py` | Simplify | Remove command listener and Playwright fallbacks. |
| Scraper | `code/scraper.py` | Simplify | Remove `book_slot()` and Playwright session renewal. |
| Notifier | `code/notifier.py` | Simplify | Remove `/agendar_...` links and command polling. |
| Workflow | `.github/workflows/check.yml` | Update | Set cron `*/20 * * * *`, remove Playwright install steps. |
| Documentation | `README.md` | Create/Update | Add DevTools cookie extraction guide. |

---

## 5. Verification Plan

1. **Unit Test Verification**:
   - Verify schedule filter: Mon-Fri 06:00 (True), 06:59 (True), 07:00 (False), 12:00 (False), 16:59 (False), 17:00 (True), 18:30 (True).
   - Verify weekend filter: Sat/Sun any hour (True).
   - Verify deduplication logic: identical slots yield no new alerts; incremented slots trigger alerts.
2. **Execution Verification**:
   - Run `python code/main.py --once` with mock/valid cookies to confirm clean exit code 0 and proper output formatting.
