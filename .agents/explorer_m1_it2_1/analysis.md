# Analysis Report — Legacy Test Purge & Worker Instructions

**Agent**: `teamwork_preview_explorer`  
**Working Directory**: `j:\Mi unidad\Natacion Colsubsidio\.agents\explorer_m1_it2_1`  
**Date**: 2026-08-11  
**Target Files**: `harness/tests/test_e2e_requirements.py`, `harness/tests/test_m2_adversarial.py`

---

## 1. Executive Summary

Milestone 1 Iteration 1 implementation code in `code/` (`config.py`, `scraper.py`, `main.py`, `notifier.py`) successfully refactored availability API scraping and removed legacy reservation/booking features. However, the Forensic Auditor (`auditor_m1_1`) issued an **INTEGRITY VIOLATION** verdict because three obsolete test cases referencing deleted functions/variables remained in `harness/tests/`.

This investigation analyzed `harness/tests/` to formulate precise worker instructions for purging all legacy reservation test cases and aligning message assertions with `code/notifier.py`.

---

## 2. Evidence & Root Cause Breakdown

### Item 1: `test_tier4_interactive_telegram_command_handling`
- **File**: `harness/tests/test_e2e_requirements.py`
- **Lines**: 600–638
- **Root Cause**: Tests the deleted Telegram `/agendar` interactive command parser, sets deleted `config.COLSUBSIDIO_TIQUETERA_ID`, and asserts invocation of deleted `scraper.book_slot()`.
- **Requirement Constraint**: `PROJECT.md` Feature F2 ("Remove `book_slot()`, `/agendar` Telegram command parser, `COLSUBSIDIO_TIQUETERA_ID`, and associated tests/secrets").
- **Action**: Completely delete lines 600–638 (the entire function and its 5 `@patch` decorators).

### Item 2: Booking Link Assertion in `test_tier3_clean_message_formatting`
- **File**: `harness/tests/test_e2e_requirements.py`
- **Line**: 382
- **Root Cause**: Line 382 asserts `assert "🔗 _Reserva en la Tienda de Diversión Colsubsidio_" in text`. Per Feature F4 / R3, booking links were removed from `code/notifier.py` to keep notification messages short and clean. Asserting this string causes assertion failure.
- **Requirement Constraint**: `PROJECT.md` Feature F4 ("Short structured Telegram messages (Date, Time, Venue, Free Slots), removing booking links").
- **Action**: Delete line 382 from `test_tier3_clean_message_formatting`.

### Item 3: `test_tiquetera_id_invalid_string_defaults_to_none`
- **File**: `harness/tests/test_m2_adversarial.py`
- **Lines**: 56–64
- **Root Cause**: Tests environment variable parsing logic for `COLSUBSIDIO_TIQUETERA_ID`. Since `COLSUBSIDIO_TIQUETERA_ID` has been removed from `code/config.py`, this test is obsolete.
- **Requirement Constraint**: `PROJECT.md` Feature F2 ("Remove `book_slot()`, `/agendar` Telegram command parser, `COLSUBSIDIO_TIQUETERA_ID`, and associated tests/secrets").
- **Action**: Completely delete lines 56–64.

---

## 3. Worker Instructions

### Edit Target 1: `harness/tests/test_e2e_requirements.py`

#### Edit 1A: Remove obsolete booking link assertion in `test_tier3_clean_message_formatting`
- **Lines**: 377–383
- **Target Content**:
```python
    assert "🏊 *¡Cupos Libres de Natación!*" in text
    assert "📍 *Sede:* EL CUBO" in text
    assert "📅 *Lunes 2026-08-24:*" in text
    assert "• ⏰ `18:00` — 🎟️ `4` cupos" in text
    assert "• ⏰ `19:00` — 🎟️ `2` cupos" in text
    assert "🔗 _Reserva en la Tienda de Diversión Colsubsidio_" in text
```
- **Replacement Content**:
```python
    assert "🏊 *¡Cupos Libres de Natación!*" in text
    assert "📍 *Sede:* EL CUBO" in text
    assert "📅 *Lunes 2026-08-24:*" in text
    assert "• ⏰ `18:00` — 🎟️ `4` cupos" in text
    assert "• ⏰ `19:00` — 🎟️ `2` cupos" in text
```

#### Edit 1B: Purge `test_tier4_interactive_telegram_command_handling`
- **Lines**: 600–638
- **Target Content**:
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
- **Replacement Content**: *(Empty string — complete removal)*

---

### Edit Target 2: `harness/tests/test_m2_adversarial.py`

#### Edit 2A: Purge `test_tiquetera_id_invalid_string_defaults_to_none`
- **Lines**: 56–64
- **Target Content**:
```python
def test_tiquetera_id_invalid_string_defaults_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que una tiquetera ID no numérica se evalúe como None en config."""
    monkeypatch.setenv("COLSUBSIDIO_TIQUETERA_ID", "invalid_id_abc")
    
    # Recargar o reler la lógica de config para COLSUBSIDIO_TIQUETERA_ID
    _tiq_val = os.environ.get("COLSUBSIDIO_TIQUETERA_ID") or "6370683"
    tiquetera_id = int(_tiq_val) if _tiq_val.isdigit() else None
    assert tiquetera_id is None
```
- **Replacement Content**: *(Empty string — complete removal)*

---

## 4. Post-Edit Verification Commands

After applying edits, the worker must run the test suite to verify 100% pass:

```bash
python -m pytest harness/tests/test_e2e_requirements.py harness/tests/test_m2_adversarial.py
```

Expected result: All tests pass with 0 failures or errors.
