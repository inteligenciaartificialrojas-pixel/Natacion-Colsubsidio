# Handoff Report: Milestone 1 Analysis & Implementation Plan

## 1. Observation
Direct codebase inspection confirmed the exact locations of legacy reservation logic and cookie-authenticated scraper structures:

1. **`code/config.py`**:
   - Lines 32–33 define legacy ticket ID:
     ```python
     _tiq_val = os.environ.get("COLSUBSIDIO_TIQUETERA_ID") or "6370683"
     COLSUBSIDIO_TIQUETERA_ID: int | None = int(_tiq_val) if _tiq_val.isdigit() else None
     ```

2. **`code/scraper.py`**:
   - Lines 245–345 contain `book_slot()` method performing `POST /v1/centro_entrenamiento/{service_id}/practicalibre/reservar`.
   - Lines 109–147 (`fetch_available_dates`) and 158–244 (`fetch_slots_for_date`) already query REST endpoints (`/calendario` and `/disponibilidad`) with session cookie headers (`sistema`, `Csrf-Token`) and handle HTTP 401 via `SessionExpiredException`.

3. **`code/main.py`**:
   - Lines 247–280 handle `/agendar` interactive Telegram reservation command matching `r"^/agendar_(\d+)_(\d{4}_\d{2}_\d{2})_(\d{2}_\d{2})$"` and calling `scraper.book_slot`.

4. **`code/notifier.py`**:
   - Lines 184–188 append interactive reservation links to notification messages:
     ```python
     command = f"/agendar_{service_id}_{date_key}_{time_key}"
     lines.append(f"• ⏰ `{s['hora']}` 🎟️ `{s['cupos']}` cupos 👉 {command}")
     ```

5. **`.github/workflows/check.yml`**:
   - Line 67 injects `COLSUBSIDIO_TIQUETERA_ID: ${{ secrets.COLSUBSIDIO_TIQUETERA_ID }}` into environment variables.

6. **`harness/tests/test_scraper.py`**:
   - Lines 128–161 (`test_book_slot_success`) and lines 248–283 (`test_book_slot_auto_retry_success`) test reservation booking logic.

---

## 2. Logic Chain
1. **Scope Definition**: The objective of Milestone 1 is to simplify the scraper to function exclusively as a read-only availability checker and to remove all ticket reservation and booking code (F1, F2).
2. **Scraper Refactoring (F1)**:
   - `fetch_available_dates` and `fetch_slots_for_date` in `code/scraper.py` correctly target REST endpoints `/v1/centro_entrenamiento/{id}/practicalibre/calendario` and `/disponibilidad?filtrarSinCupo=0`.
   - Session cookies (`sistema` and `Csrf-Token`) are correctly formatted into requests cookies and headers, with auto-retry and Playwright session renewal on HTTP 401 / `SessionExpiredException`.
3. **Legacy Code Removal (F2)**:
   - `book_slot()` in `code/scraper.py` is the sole entry point for sending reservation POST requests to Colsubsidio. Deleting it completes the scraper simplification.
   - `COLSUBSIDIO_TIQUETERA_ID` in `code/config.py` and `.github/workflows/check.yml` is no longer needed.
   - `/agendar` command parser in `code/main.py` and `/agendar` command formatting in `code/notifier.py` are part of the interactive reservation workflow. Purging them cleans Telegram alerts and removes unused command loops.
   - `test_book_slot_success` and `test_book_slot_auto_retry_success` in `harness/tests/test_scraper.py` must be removed so the test suite passes cleanly after `book_slot` is deleted.

---

## 3. Caveats
- `COLSUBSIDIO_DOCUMENT_TYPE` and `COLSUBSIDIO_DOCUMENT_NUMBER` must **not** be removed from `code/config.py` because `fetch_slots_for_date()` requires `persona` data in its request body to retrieve valid slot availability for document holders.
- `get_incoming_commands` in `code/notifier.py` can remain as a utility function, but its call in `code/main.py` should no longer trigger reservation actions.

---

## 4. Conclusion
Milestone 1 is fully specified and ready for Worker execution. All target files, line numbers, and exact code deletions/refactorings have been mapped in `analysis.md`. Proceeding with Worker implementation will achieve 100% compliance with Feature 1 and Feature 2 without breaking existing availability polling or Telegram alert mechanisms.

---

## 5. Verification Method
Worker can verify implementation by executing:
1. **Pytest Test Suite Run**:
   ```bash
   pytest harness/tests/test_scraper.py harness/tests/test_notifier.py harness/tests/test_orchestrator.py
   ```
2. **Codebase Grep Check**:
   Confirm 0 matches for `book_slot` or `COLSUBSIDIO_TIQUETERA_ID` across `code/` and `.github/`.
3. **Dry-run Execution**:
   ```bash
   python code/main.py --once
   ```
   (Verify clean availability check without reservation command outputs or errors).
