# Test Suite Legacy Code Purge Analysis & Worker Instructions

**Agent**: `teamwork_preview_explorer` (Explorer Iteration `explorer_m1_it2_2`)  
**Working Directory**: `j:\Mi unidad\Natacion Colsubsidio\.agents\explorer_m1_it2_2`  
**Target Subsystem**: `harness/tests/`  
**Date**: 2026-08-11  

---

## 1. Executive Summary & Findings

A comprehensive inspection of all 11 test files within `harness/tests/` was conducted to identify obsolete references to `book_slot()`, `COLSUBSIDIO_TIQUETERA_ID`, interactive `/agendar` Telegram command handling, and legacy booking assertion logic.

While the core implementation code (`code/scraper.py`, `code/config.py`, `code/main.py`, `code/notifier.py`) was cleanly refactored in Milestone 1 to focus strictly on session cookie availability scraping and Telegram notifications, residual legacy test code remained in the test suite, causing test failures (`AttributeError` when attempting to access `config.COLSUBSIDIO_TIQUETERA_ID` or `scraper.book_slot`).

### Audit Summary Matrix

| Test File | Status | Legacy Code Present | Action Required |
|---|---|---|---|
| `harness/tests/test_e2e_requirements.py` | **ACTION REQUIRED** | Lines 605–638 (`test_tier4_interactive_telegram_command_handling`) | **Delete function** |
| `harness/tests/test_m2_adversarial.py` | **ACTION REQUIRED** | Lines 56–64 (`test_tiquetera_id_invalid_string_defaults_to_none`) | **Delete function** |
| `harness/tests/test_m3_adversarial_challenger.py` | **ACTION REQUIRED** | Line 4 (Docstring summary reference to `book_slot`) | **Clean docstring** |
| `harness/tests/test_m3_challenger_session.py` | **ACTION REQUIRED** | Lines 7, 8, 11, 14 (Docstring references to `book_slot`/`reservar`) | **Clean docstring** |
| `harness/tests/test_dummy.py` | **CLEAN** | None | No action |
| `harness/tests/test_get_cookies.py` | **CLEAN** | None | No action |
| `harness/tests/test_get_cookies_adversarial.py` | **CLEAN** | None | No action |
| `harness/tests/test_m4_cicd_local_runner.py` | **CLEAN** | None | No action |
| `harness/tests/test_notifier.py` | **CLEAN** | None | No action |
| `harness/tests/test_orchestrator.py` | **CLEAN** | None | No action |
| `harness/tests/test_scraper.py` | **CLEAN** | None | No action |

---

## 2. Detailed Legacy Locations & Analysis

### Location 1: `harness/tests/test_e2e_requirements.py` (Lines 605–638)
- **Code Snippet**:
  ```python
  @patch("main.save_cooldown_state")
  @patch("main.load_cooldown_state")
  @patch("main.check_venues")
  @patch("main.TelegramNotifier")
  @patch("main.ColsubsidioScraper")
  def test_tier4_interactive_telegram_command_handling(
      mock_scraper_cls: MagicMock,
      mock_notifier_cls: MagicMock,
      mock_check: MagicMock,
      mock_load_state: MagicMock,
      mock_save_state: MagicMock,
      monkeypatch: pytest.MonkeyPatch
  ) -> None:
      """Verifica el procesamiento de comandos interactivos Telegram (/agendar) en main()."""
      monkeypatch.setattr("sys.argv", ["main.py", "--once"])
      monkeypatch.setattr("config.COLSUBSIDIO_TIQUETERA_ID", 6370683)

      mock_load_state.return_value = {"last_expiry_alert_time": 0.0, "last_processed_update_id": 0}

      notifier_inst = mock_notifier_cls.return_value
      notifier_inst.chat_id = "12345"
      notifier_inst.get_incoming_commands.return_value = [
          {
              "update_id": 500,
              "message": {
                  "chat": {"id": "12345"},
                  "text": "/agendar_232_2026_08_24_18_00"
              }
          }
      ]

      scraper_inst = mock_scraper_cls.return_value
      scraper_inst.book_slot.return_value = (True, "Reserva confirmada")

      main()

      scraper_inst.book_slot.assert_called_once_with(232, "2026-08-24", "18:00", 6370683)
      assert notifier_inst.send_message.call_count >= 2
  ```
- **Reason for Removal**: Feature F2 in `PROJECT.md` mandates the complete removal of reservation logic, `/agendar` parsing, and `book_slot()`. This test function fails when executed because `config.COLSUBSIDIO_TIQUETERA_ID` and `scraper.book_slot` no longer exist.

### Location 2: `harness/tests/test_m2_adversarial.py` (Lines 56–64)
- **Code Snippet**:
  ```python
  def test_tiquetera_id_invalid_string_defaults_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
      """Verifica que una tiquetera ID no numérica se evalúe como None en config."""
      monkeypatch.setenv("COLSUBSIDIO_TIQUETERA_ID", "invalid_id_abc")
      
      # Recargar o reler la lógica de config para COLSUBSIDIO_TIQUETERA_ID
      _tiq_val = os.environ.get("COLSUBSIDIO_TIQUETERA_ID") or "6370683"
      tiquetera_id = int(_tiq_val) if _tiq_val.isdigit() else None
      assert tiquetera_id is None
  ```
- **Reason for Removal**: `COLSUBSIDIO_TIQUETERA_ID` has been removed from `code/config.py`. Testing its environment fallback is obsolete.

### Location 3: `harness/tests/test_m3_adversarial_challenger.py` (Line 4)
- **Docstring snippet**:
  `4. 401 persistentes (agotamiento de reintentos, comportamiento en book_slot, fetch_available_dates y fetch_slots_for_date).`
- **Reason for Update**: Remove reference to `book_slot` in the file docstring.

### Location 4: `harness/tests/test_m3_challenger_session.py` (Lines 7, 8, 11, 14)
- **Docstring snippets**:
  - Line 7: `4. Preservación de estado de sesión en el flujo de 2 pasos de book_slot.`
  - Line 8: `5. Renovación de sesión en el paso 1 (disponibilidad) vs paso 2 (reservar) en book_slot.`
  - Line 11: `6. Reservas secuenciales múltiples con la misma instancia de scraper.`
  - Line 14: `11. Detección de sesión expirada vía JSON Unauthorized y HTML loguearSitio en book_slot.`
- **Reason for Update**: Clean the module docstring summary so it accurately reflects the availability and session monitoring tests actually contained in the file.

---

## 3. Worker Action Plan

Worker should perform the following changes:

1. **Modify `harness/tests/test_e2e_requirements.py`**:
   - Remove lines 600–638 containing `test_tier4_interactive_telegram_command_handling`.

2. **Modify `harness/tests/test_m2_adversarial.py`**:
   - Remove lines 56–64 containing `test_tiquetera_id_invalid_string_defaults_to_none`.

3. **Modify `harness/tests/test_m3_adversarial_challenger.py`**:
   - Update line 4 of module docstring to remove `book_slot`.

4. **Modify `harness/tests/test_m3_challenger_session.py`**:
   - Update lines 7–14 of module docstring to remove obsolete `book_slot`/reservation bullets.

5. **Verification**:
   - Run `python -m pytest harness/tests/` to verify 100% pass rate across all test modules.
