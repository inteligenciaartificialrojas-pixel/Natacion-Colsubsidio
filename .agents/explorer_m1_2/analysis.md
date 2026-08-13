# Analysis Report — Milestone 1: Legacy Code Removal in CLI & Notifier Modules

**Agent**: `teamwork_preview_explorer` (`explorer_m1_2`)  
**Date**: 2026-08-11  
**Target Milestone**: M1 (Scraper Refactoring & Legacy Code Removal — Feature F2)  
**Working Directory**: `j:\Mi unidad\Natacion Colsubsidio\.agents\explorer_m1_2`

---

## 1. Executive Summary

Feature **F2 (Legacy Reservation Code Removal)** mandates the total purge of interactive booking handlers, tiquetera consumption code, and legacy booking URLs from the Colsubsidio Swimming Availability Monitor. The system scope has been focused strictly on read-only availability monitoring with clean Telegram alerts.

This analysis identifies all legacy components across `code/main.py`, `code/notifier.py`, `code/config.py`, `code/scraper.py`, `.github/workflows/check.yml`, and `harness/tests/`, providing step-by-step instructions and code diff specifications for the Worker implementation.

---

## 2. File-by-File Technical Analysis & Proposed Modifications

### 2.1 `code/main.py`
- **Location**: `code/main.py`, lines 229–280 (in `main()`), lines 38–50 (in `load_cooldown_state()`).
- **Current State**:
  - `load_cooldown_state()` sets `"last_processed_update_id": 0` in default state dict.
  - In `main()`, step 1 polls incoming Telegram messages via `notifier.get_incoming_commands(offset=offset)` and matches regex `^/agendar_(\d+)_(\d{4}_\d{2}_\d{2})_(\d{2}_\d{2})$`.
  - Upon match, imports `COLSUBSIDIO_TIQUETERA_ID` from `config`, sends progress alert, calls `scraper.book_slot(...)`, and notifies Telegram of success/failure.
- **Required Modifications**:
  - Purge lines 229–280 entirely from `main()`. Remove incoming command listener logic.
  - Update `load_cooldown_state()` default dict to remove `"last_processed_update_id": 0` (or preserve key for backwards compatibility if needed, but remove polling calls).
- **Proposed Snippet (Before -> After)**:

*Before (`code/main.py` lines 228–280)*:
```python
    interval = DEFAULT_CHECK_INTERVAL_SECONDS
    state = load_cooldown_state()

    # 1. Procesar comandos interactivos de Telegram antes de hacer el chequeo
    offset = state.get("last_processed_update_id", 0) + 1
    updates = notifier.get_incoming_commands(offset=offset)

    for update in updates:
        update_id = update.get("update_id")
        if update_id:
            state["last_processed_update_id"] = max(state["last_processed_update_id"], update_id)

        message = update.get("message", {})
        text = message.get("text", "").strip()
        chat_id = message.get("chat", {}).get("id")

        # Seguridad: Solo procesar comandos del chat_id autorizado
        if str(chat_id) != str(notifier.chat_id):
            continue

        # Match del comando de agendamiento (/agendar_ID_YYYY_MM_DD_HH_MM)
        match = re.match(r"^/agendar_(\d+)_(\d{4}_\d{2}_\d{2})_(\d{2}_\d{2})$", text)
        if match:
            ...
            success, msg = scraper.book_slot(service_id, date_str, time_str, COLSUBSIDIO_TIQUETERA_ID)
            ...

    # 2. Calcular hora local de Colombia (Bogotá UTC-5)
```

*After (`code/main.py`)*:
```python
    interval = DEFAULT_CHECK_INTERVAL_SECONDS
    state = load_cooldown_state()

    # 1. Calcular hora local de Colombia (Bogotá UTC-5)
```

---

### 2.2 `code/notifier.py`
- **Location**: `code/notifier.py`, lines 75–104 (`get_incoming_commands`), lines 184–188 and 191 (`notify_venue_slots`).
- **Current State**:
  - `get_incoming_commands()` queries `https://api.telegram.org/bot<token>/getUpdates` to fetch `/agendar` commands.
  - `notify_venue_slots()` constructs interactive command strings `date_key`, `time_key`, `command = f"/agendar_{service_id}_{date_key}_{time_key}"` and formats lines as:
    `lines.append(f"• ⏰ `{s['hora']}` 🎟️ `{s['cupos']}` cupos 👉 {command}")`
  - Includes footer link: `lines.append("🔗 _Reserva en la Tienda de Diversión Colsubsidio_")`.
- **Required Modifications**:
  - Remove `get_incoming_commands(self, offset: int = 0)` method entirely.
  - In `notify_venue_slots()`, remove `service_id` lookup for `/agendar` commands, remove `date_key`/`time_key`/`command` construction, and format slot lines cleanly without interactive commands:
    `lines.append(f"• ⏰ `{s['hora']}` — 🎟️ `{s['cupos']}` cupos")`
  - Remove interactive booking links from notification output.
- **Proposed Snippet (Before -> After)**:

*Before (`code/notifier.py` lines 183–191)*:
```python
            lines.append(date_header)
            for s in date_slots:
                # Generar link interactivo de comando para Telegram (ej. /agendar_229_2026_06_12_18_00)
                date_key = date_str.replace("-", "_")
                time_key = s["hora"].replace(":", "_")
                command = f"/agendar_{service_id}_{date_key}_{time_key}"
                lines.append(f"• ⏰ `{s['hora']}` 🎟️ `{s['cupos']}` cupos 👉 {command}")
            lines.append("")  # Espacio entre fechas

        lines.append("🔗 _Reserva en la Tienda de Diversión Colsubsidio_")
```

*After (`code/notifier.py`)*:
```python
            lines.append(date_header)
            for s in date_slots:
                lines.append(f"• ⏰ `{s['hora']}` — 🎟️ `{s['cupos']}` cupos")
            lines.append("")  # Espacio entre fechas
```

---

### 2.3 `code/config.py`
- **Location**: `code/config.py`, lines 31–33.
- **Current State**:
  ```python
  # ID de la tiquetera/plan para reservas automatizadas/interactivas
  _tiq_val = os.environ.get("COLSUBSIDIO_TIQUETERA_ID") or "6370683"
  COLSUBSIDIO_TIQUETERA_ID: int | None = int(_tiq_val) if _tiq_val.isdigit() else None
  ```
- **Required Modifications**:
  - Remove `_tiq_val` and `COLSUBSIDIO_TIQUETERA_ID` definitions completely.

---

### 2.4 `code/scraper.py`
- **Location**: `code/scraper.py`, lines 245–345 (`book_slot`).
- **Current State**:
  - `book_slot(self, service_id: int, date_str: str, time_str: str, tiquetera_id: int)` sends POST requests to `/v1/centro_entrenamiento/{service_id}/practicalibre/reservar` to execute slot bookings.
- **Required Modifications**:
  - Purge `book_slot()` method completely.

---

### 2.5 `.github/workflows/check.yml`
- **Location**: `.github/workflows/check.yml`, line 67.
- **Current State**:
  ```yaml
        COLSUBSIDIO_USER: ${{ secrets.COLSUBSIDIO_USER }}
        COLSUBSIDIO_PASS: ${{ secrets.COLSUBSIDIO_PASS }}
        COLSUBSIDIO_SISTEMA_COOKIE: ${{ secrets.COLSUBSIDIO_SISTEMA_COOKIE }}
        COLSUBSIDIO_CSRF_TOKEN: ${{ secrets.COLSUBSIDIO_CSRF_TOKEN }}
        COLSUBSIDIO_DOCUMENT_TYPE: ${{ secrets.COLSUBSIDIO_DOCUMENT_TYPE }}
        COLSUBSIDIO_DOCUMENT_NUMBER: ${{ secrets.COLSUBSIDIO_DOCUMENT_NUMBER }}
        COLSUBSIDIO_TIQUETERA_ID: ${{ secrets.COLSUBSIDIO_TIQUETERA_ID }}
  ```
- **Required Modifications**:
  - Remove `COLSUBSIDIO_TIQUETERA_ID: ${{ secrets.COLSUBSIDIO_TIQUETERA_ID }}` secret mapping.

---

### 2.6 `harness/tests/` (Test Suite Alignment)
- **Files Affected**:
  - `harness/tests/test_notifier.py`: Remove `test_get_incoming_commands_success` (lines 113–142).
  - `harness/tests/test_scraper.py`: Remove `test_book_slot_success` (lines 127–162) and `test_book_slot_auto_retry_success` (lines 248–283).
  - `harness/tests/test_m3_adversarial_challenger.py`: Remove `test_persistent_401_in_book_slot_raises_exception` (lines 70–105).
  - `harness/tests/test_m3_challenger_session.py`: Remove section 3 `test_book_slot_*` tests (lines 190–399).
- **Rationale**: Purging legacy functions (`book_slot`, `get_incoming_commands`) requires updating unit tests so pytest continues to run 100% clean without failing on missing attributes.

---

## 3. Impact Assessment & Risk Mitigation

| Area | Impact | Mitigation |
|---|---|---|
| CLI Runtime (`main.py`) | High reduction in code complexity; removes network call to Telegram `getUpdates` on every loop iteration. | Verify `--once` execution runs cleanly without `last_processed_update_id`. |
| Notifications (`notifier.py`) | Cleaner Markdown output; prevents user confusion with non-functional `/agendar` commands. | Run `pytest harness/tests/test_notifier.py` to confirm clean formatting. |
| Configuration (`config.py`) | Eliminates unused environment variable. | Ensure no other module imports `COLSUBSIDIO_TIQUETERA_ID`. |
| CI/CD (`check.yml`) | Simplifies secret requirements. | Validate YAML syntax and secret list against `PROJECT.md` M1 specifications. |

---

## 4. Step-by-Step Worker Implementation Instructions

1. **Modify `code/config.py`**:
   - Delete `COLSUBSIDIO_TIQUETERA_ID` lines 31–33.
2. **Modify `code/scraper.py`**:
   - Delete `book_slot` method (lines 245–345).
3. **Modify `code/notifier.py`**:
   - Delete `get_incoming_commands` method (lines 75–104).
   - In `notify_venue_slots`, remove `/agendar` command string building and update slot formatting to `• ⏰ {s['hora']} — 🎟️ {s['cupos']} cupos`. Remove booking URL footer line.
4. **Modify `code/main.py`**:
   - In `main()`, remove block 1 (command processing loop lines 229–280).
   - In `load_cooldown_state()`, remove `last_processed_update_id` default key if desired, or keep as optional fallback.
5. **Modify `.github/workflows/check.yml`**:
   - Remove `COLSUBSIDIO_TIQUETERA_ID: ${{ secrets.COLSUBSIDIO_TIQUETERA_ID }}` under `Ejecutar Revisor` step env.
6. **Update Test Suite (`harness/tests/`)**:
   - Remove obsolete unit and challenger tests for `book_slot` and `get_incoming_commands`.
7. **Verification**:
   - Run `py -m pytest harness/tests` to verify test suite passes 100%.
