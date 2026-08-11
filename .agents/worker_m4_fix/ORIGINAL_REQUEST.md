## 2026-08-09T19:00:13Z
You are Worker M4 Fix (teamwork_preview_worker) for Milestone 4 Remediation.
Working directory: i:\Mi unidad\Natacion Colsubsidio\.agents\worker_m4_fix

Your task is to fix the issues identified by Reviewers and Challengers in Milestone 4:

1. **Fix `.github/workflows/check.yml`**:
   - Replace invalid/non-existent GitHub Action tags:
     - `actions/checkout@v5` -> `actions/checkout@v4`
     - `actions/setup-python@v6` -> `actions/setup-python@v5`
     - `actions/cache/restore@v5` and `actions/cache/save@v5` -> use standard `actions/cache@v4` with key `playwright-${{ runner.os }}-${{ hashFiles('code/requirements.txt') }}` and restore-keys `playwright-${{ runner.os }}-`.
   - Ensure `COLSUBSIDIO_USER` and `COLSUBSIDIO_PASS` secrets are bound under `Ejecutar Revisor` step running `python code/main.py --once`.
   - Ensure Playwright Chromium install step runs `python -m playwright install --with-deps chromium`.

2. **Fix `actualizar_cookies.bat` and `ejecutar_revisor_local.bat`**:
   - Add `cd /d "%~dp0"` at the beginning of both batch scripts to ensure execution from the project directory.
   - Remove hardcoded user path (`C:\Users\andre\...`) and use clean Python executable resolution (`python` from PATH or py launcher).
   - In `ejecutar_revisor_local.bat`, check `if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%` after `get_cookies.py` execution so that failures abort cleanly.

3. **Fix `code/get_cookies.py` Cookie Logging**:
   - Do NOT print raw sensitive cookie values (`sistema` or `Csrf-Token`) in stdout/logging. Log presence/length or truncated hashes instead (e.g. `sistema cookie captured (len=...)`).

4. **Update `harness/tests/test_m4_cicd_local_runner.py`**:
   - Update test cases to verify that `.github/workflows/check.yml` uses valid action tags (`@v4`, `@v5`), batch scripts contain `cd /d "%~dp0"`, and all tests pass.

5. **Run test suite**:
   - Execute `py -m pytest harness/tests` or `pytest harness/tests` to confirm 100% pass rate across all tests.

6. **MANDATORY INTEGRITY WARNING**: DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

7. Write your handoff report to `i:\Mi unidad\Natacion Colsubsidio\.agents\worker_m4_fix\handoff.md` and send message to parent.
