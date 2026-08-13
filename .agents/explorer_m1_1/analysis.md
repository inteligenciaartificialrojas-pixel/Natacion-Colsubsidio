# Technical Analysis & Implementation Instructions: Milestone 1

## Overview
**Milestone 1** focuses on two primary objectives:
1. **Scraper Refactoring (F1)**: Validating and solidifying the cookie session authentication and REST availability endpoint client (`/calendario` and `/disponibilidad`), ensuring clean read-only status and robust 401 handling.
2. **Legacy Reservation Removal (F2)**: Completely purging all legacy reservation code (`book_slot`, `COLSUBSIDIO_TIQUETERA_ID`, `/agendar` command handlers, and reservation test cases).

---

## 1. Scraper Refactoring Specification (`code/scraper.py` & `code/config.py`)

### 1.1 Endpoint & Header Architecture
- **Authentication**: Uses `COLSUBSIDIO_SISTEMA_COOKIE` (mapped to cookie `sistema`) and `COLSUBSIDIO_CSRF_TOKEN` (mapped to cookie `Csrf-Token` and HTTP header `Csrf-Token`).
- **Endpoint 1 (Date Availability Calendar)**:
  - **URL**: `POST https://www.diversioncolsubsidio.com/v1/centro_entrenamiento/{service_id}/practicalibre/calendario`
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
  - **Response Processing**: Extracts keys in `data.fechas` where `disponibilidad` is `True`.

- **Endpoint 2 (Time Slot & Capacity Availability)**:
  - **URL**: `POST https://www.diversioncolsubsidio.com/v1/centro_entrenamiento/{service_id}/practicalibre/disponibilidad?filtrarSinCupo=0`
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
        "persona": [
          {
            "tipo_documento": "CC",
            "documento": "...",
            "datos": {}
          }
        ]
      }
    }
    ```
  - **Response Processing**: Parses `data.horarios`, normalizes `hora_inicio` to `HH:MM`, sums available capacity per zone/lane, and returns `[{"fecha": date_str, "hora": hora_formatted, "cupos": cupos}]`.

- **Session Expiration & Resiliency**:
  - `_check_unauthorized()` inspects HTTP status code 401, JSON status `"Unauthorized"`, or HTML login redirection.
  - On 401, raises `SessionExpiredException`.
  - `_execute_with_retry()` catches `SessionExpiredException`, calls `_renew_session()` via Playwright cookie renewal, updates in-memory headers/cookies, and retries the request once.

---

## 2. Legacy Reservation Removal Instructions

Worker must perform surgical code updates across 6 target files to eliminate all booking/reservation logic:

### 2.1 File 1: `code/config.py`
- **Target Lines**: 31–34
- **Action**: Delete the definition of `COLSUBSIDIO_TIQUETERA_ID`.
- **Target Content to Remove**:
  ```python
  # ID de la tiquetera/plan para reservas automatizadas/interactivas
  _tiq_val = os.environ.get("COLSUBSIDIO_TIQUETERA_ID") or "6370683"
  COLSUBSIDIO_TIQUETERA_ID: int | None = int(_tiq_val) if _tiq_val.isdigit() else None
  ```
- **Preserved Content**: Keep `COLSUBSIDIO_DOCUMENT_TYPE` and `COLSUBSIDIO_DOCUMENT_NUMBER` as they are used in `fetch_slots_for_date`.

### 2.2 File 2: `code/scraper.py`
- **Target Lines**: 245–345
- **Action**: Delete `book_slot()` method completely.
- **Target Content to Remove**:
  ```python
  def book_slot(self, service_id: int, date_str: str, time_str: str, tiquetera_id: int) -> tuple[bool, str]:
      ...
  ```
- **Result**: `ColsubsidioScraper` becomes a pure read-only availability polling client.

### 2.3 File 3: `code/main.py`
- **Target Lines**: 247–280
- **Action**: Remove the `/agendar` Telegram command processing block.
- **Target Content to Remove**:
  ```python
  # Match del comando de agendamiento (/agendar_ID_YYYY_MM_DD_HH_MM)
  match = re.match(r"^/agendar_(\d+)_(\d{4}_\d{2}_\d{2})_(\d{2}_\d{2})$", text)
  if match:
      ...
  ```
- **Cleaned Command Loop**: Keep update ID tracking or simplify incoming update processing without attempting slot reservations.

### 2.4 File 4: `code/notifier.py`
- **Target Lines**: 184–188
- **Action**: Remove `/agendar` command link appending in `notify_venue_slots`.
- **Original Content**:
  ```python
  # Generar link interactivo de comando para Telegram (ej. /agendar_229_2026_06_12_18_00)
  date_key = date_str.replace("-", "_")
  time_key = s["hora"].replace(":", "_")
  command = f"/agendar_{service_id}_{date_key}_{time_key}"
  lines.append(f"• ⏰ `{s['hora']}` 🎟️ `{s['cupos']}` cupos 👉 {command}")
  ```
- **Replacement Content**:
  ```python
  lines.append(f"• ⏰ `{s['hora']}` — 🎟️ `{s['cupos']}` cupos")
  ```

### 2.5 File 5: `.github/workflows/check.yml`
- **Target Line**: 67
- **Action**: Remove `COLSUBSIDIO_TIQUETERA_ID` secret environment injection.
- **Target Content to Remove**:
  ```yaml
  COLSUBSIDIO_TIQUETERA_ID: ${{ secrets.COLSUBSIDIO_TIQUETERA_ID }}
  ```

### 2.6 File 6: `harness/tests/test_scraper.py`
- **Target Lines**: 128–161 & 248–283
- **Action**: Remove obsolete reservation tests `test_book_slot_success` and `test_book_slot_auto_retry_success`.

---

## 3. Verification & Acceptance Criteria
- Run unit tests using `pytest harness/tests/`:
  - `pytest harness/tests/test_scraper.py`
  - `pytest harness/tests/test_notifier.py`
  - `pytest harness/tests/test_orchestrator.py`
- Verify zero references to `book_slot` or `COLSUBSIDIO_TIQUETERA_ID` remain in active runtime code.
- Ensure scraper functions `fetch_available_dates` and `fetch_slots_for_date` execute cleanly without reservation dependencies.
