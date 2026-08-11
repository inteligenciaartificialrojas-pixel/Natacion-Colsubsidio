## 2026-08-09T18:24:51Z

You are Worker M2 for Milestone 2: Playwright Automated Login & Session Renewal Module.
Your Working Directory: `i:\Mi unidad\Natacion Colsubsidio\.agents\worker_m2`
Workspace Root: `i:\Mi unidad\Natacion Colsubsidio`
Scope Document: `i:\Mi unidad\Natacion Colsubsidio\PROJECT.md`
Original Request: `i:\Mi unidad\Natacion Colsubsidio\.agents\ORIGINAL_REQUEST.md`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Assigned Task:
1. Read Explorer handoff reports at `i:\Mi unidad\Natacion Colsubsidio\.agents\explorer_m1_1\handoff.md` and `i:\Mi unidad\Natacion Colsubsidio\.agents\explorer_m1_3\handoff.md`.
2. Update `code/config.py` to support `COLSUBSIDIO_USER` and `COLSUBSIDIO_PASS` environment variables.
3. Implement `login_and_get_cookies(user=None, password=None, headless=True)` in `code/get_cookies.py` using Playwright Chromium (`playwright.sync_api`).
   - Authenticate on `https://www.diversioncolsubsidio.com/sistema.php/default/loguearSitio` using credentials `COLSUBSIDIO_USER` / `COLSUBSIDIO_PASS` or arguments.
   - Extract `sistema` and `Csrf-Token` cookies.
   - Update `.env` on disk with fresh cookie values.
   - Return cookie dict `{"sistema": ..., "Csrf-Token": ...}`.
4. Ensure `extract_colsubsidio_cookies()` or `get_cookies.py` entry points use `login_and_get_cookies()` as the primary login mechanism, maintaining backwards compatibility if needed.
5. Add/update tests in `harness/tests/test_get_cookies.py` to verify cookie updates, mock Playwright browser interactions, and test error handling when credentials are missing or invalid.
6. Run the test suite (`py -m pytest harness/tests` or `pytest harness/tests`) and confirm ALL tests pass.
7. Write `changes.md` and `handoff.md` in `i:\Mi unidad\Natacion Colsubsidio\.agents\worker_m2` documenting code changes, test execution commands, and test results.
8. Send a message to parent (`2aca26f8-a79b-4b4a-a36a-921521a80c8c`) when done.
