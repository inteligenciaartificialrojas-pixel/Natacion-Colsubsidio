# DISPATCH — test_writer_e2e_1

- **Role**: teamwork_preview_test_writer
- **Working Directory**: j:\Mi unidad\Natacion Colsubsidio\.agents\test_writer_e2e_1
- **User Request Specification Path**: j:\Mi unidad\Natacion Colsubsidio\.agents\ORIGINAL_REQUEST.md
- **Project Scope Path**: j:\Mi unidad\Natacion Colsubsidio\.agents\orchestrator\PROJECT.md
- **Project Root**: j:\Mi unidad\Natacion Colsubsidio

## Objectives
1. Read `ORIGINAL_REQUEST.md` and `PROJECT.md`.
2. Design and implement an opaque-box, requirement-driven E2E test suite in `harness/tests/test_e2e_requirements.py` covering:
   - Tier 1: Availability API scraper endpoints and session cookie headers (`COLSUBSIDIO_SISTEMA_COOKIE`, `COLSUBSIDIO_CSRF_TOKEN`) (>=5 tests per feature).
   - Tier 2: Schedule filter engine rules (Mon-Fri < 07:00 or >= 17:00, Sat-Sun 24h, Colombian Holidays 24h) and edge cases.
   - Tier 3: Clean Telegram notification formatting and slot state deduplication (`.last_slots.json` / `.cooldown_state`).
   - Tier 4: End-to-end execution workflow test cases.
3. Run tests using pytest to verify harness functionality.
4. Publish `TEST_READY.md` at `j:\Mi unidad\Natacion Colsubsidio\TEST_READY.md` with coverage breakdown table.
5. Deliver `handoff.md` in your working directory.
