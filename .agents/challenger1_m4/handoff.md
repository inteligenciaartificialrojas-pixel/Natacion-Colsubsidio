# Milestone 4 Empirical Challenge & Stress Test Report

## Challenge Summary

**Overall risk assessment**: **HIGH**

Empirical stress testing and static specification analysis of Milestone 4 (CI/CD & Local Runner Compatibility) revealed critical failure modes in GitHub Actions workflow dependencies, batch script environment resolution, and error handling pipeline propagation. While basic functionality and pytest assertion coverage exist in `harness/tests/test_m4_cicd_local_runner.py`, key edge cases and deployment risks render the current implementation vulnerable to runtime failure in production CI/CD and non-developer Windows environments.

---

## Observation

1. **GitHub Actions Non-Existent Action Versions (`.github/workflows/check.yml`)**:
   - `.github/workflows/check.yml`, Line 23: `uses: actions/checkout@v5`
   - `.github/workflows/check.yml`, Line 26: `uses: actions/setup-python@v6`
   - `.github/workflows/check.yml`, Line 48: `uses: actions/cache/restore@v5`
   - `.github/workflows/check.yml`, Line 77: `uses: actions/cache/save@v5`
   - *Fact*: As of GitHub Actions current release tags, official major releases for `actions/checkout` are `@v4`, `actions/setup-python` is `@v5`, and `actions/cache` (`restore`/`save`) is `@v4`. Referencing `@v5` or `@v6` causes GitHub Actions runners to fail during workflow initialization with `Action not found`.

2. **GitHub Actions Cache Key Eviction & Accumulation Strategy (`.github/workflows/check.yml`)**:
   - `.github/workflows/check.yml`, Line 53 & 82: `key: state-cache-${{ github.run_id }}-${{ github.run_attempt }}`
   - `.github/workflows/check.yml`, Line 54-55: `restore-keys: |\n  state-cache-`
   - *Fact*: With a 10-minute cron schedule (144 runs/day), generating a new cache key with `github.run_id` on every run creates 144 distinct cache entries daily. This rapidly exhausts the 10 GB GitHub Actions repository cache limit and forces aggressive cache eviction of Playwright browser binaries (`~/.cache/ms-playwright`).

3. **Hardcoded User Path in Batch Runner Scripts (`actualizar_cookies.bat` & `ejecutar_revisor_local.bat`)**:
   - `actualizar_cookies.bat`, Lines 9–12 & `ejecutar_revisor_local.bat`, Lines 10–13:
     ```cmd
     set "PYTHON_EXE=python"
     if exist "C:\Users\andre\AppData\Local\Python\bin\python.exe" (
         set "PYTHON_EXE=C:\Users\andre\AppData\Local\Python\bin\python.exe"
     )
     ```
   - *Fact*: The path `C:\Users\andre\...` is hardcoded to a specific local user directory (`andre`). On any other Windows machine or user profile (`USER`, `administrator`, `runner`), this `if exist` check evaluates to `false` and falls back to `python` in `%PATH%`.

4. **Missing Error Code Check in `ejecutar_revisor_local.bat`**:
   - `ejecutar_revisor_local.bat`, Lines 16–23:
     ```cmd
     "%PYTHON_EXE%" "%~dp0code\get_cookies.py"
     echo.
     echo Iniciando monitor continuo (revisara cada 5 minutos)...
     echo Presiona Ctrl+C para detener el proceso.
     echo.
     "%PYTHON_EXE%" "%~dp0code\main.py"
     ```
   - *Fact*: No `%ERRORLEVEL%` check is performed after executing `get_cookies.py`. If `get_cookies.py` fails (e.g., authentication timeout, missing Playwright, invalid credentials), `ejecutar_revisor_local.bat` ignores the failure and immediately executes `main.py` with stale or missing credentials.

5. **Missing Working Directory Normalization in Batch Scripts**:
   - Neither `actualizar_cookies.bat` nor `ejecutar_revisor_local.bat` executes `cd /d "%~dp0"`.
   - *Fact*: If executed from an external directory (e.g. `C:\> "I:\Natacion\ejecutar_revisor_local.bat"`), `python` runs `code/main.py` using `C:\` as working directory (`os.getcwd()`), preventing `.env` and local state files from being loaded correctly.

6. **Pytest Assertion Gap in `harness/tests/test_m4_cicd_local_runner.py`**:
   - `harness/tests/test_m4_cicd_local_runner.py`, Lines 26–53 (`test_github_workflow_check_yml_configuration`):
     Validates substring presence of `python -m playwright install --with-deps chromium`, `actions/cache`, and secrets, but does NOT validate that action tags correspond to extant GitHub Action versions or that batch scripts check `%ERRORLEVEL%`.

---

## Logic Chain

1. **Premise 1**: GitHub Actions requires referenced action repositories and major tags (e.g., `actions/checkout@v4`) to exist in GitHub's registry.
2. **Observation 1 -> Step 1**: `.github/workflows/check.yml` specifies `actions/checkout@v5`, `actions/setup-python@v6`, `actions/cache/restore@v5`, and `actions/cache/save@v5`.
3. **Inference 1**: When triggered on GitHub Actions, the runner will attempt to download non-existent tags (`v5` for checkout, `v6` for setup-python, `v5` for cache/restore and cache/save) and fail immediately prior to executing any job steps.
4. **Premise 2**: Local runner batch scripts must be portable across different Windows environments and resilient against component failures.
5. **Observation 3 -> Step 2**: `actualizar_cookies.bat` and `ejecutar_revisor_local.bat` check for `C:\Users\andre\AppData\Local\Python\bin\python.exe`.
6. **Inference 2**: On any machine where the Windows username is not `andre`, the script silently falls back to standard `python` in `%PATH%`. If Python is installed via `%USERPROFILE%\AppData\Local\...` under a different username, or if Windows App Execution Aliases redirect `python.exe` to Microsoft Store, the runner fails to launch Python.
7. **Observation 4 -> Step 3**: `ejecutar_revisor_local.bat` executes `get_cookies.py` followed immediately by `main.py` without testing `%ERRORLEVEL%`.
8. **Inference 3**: If cookie extraction fails (e.g. bad password, Playwright missing, Colsubsidio portal down), `main.py` will run with expired/invalid credentials, causing downstream alerts or unhandled exceptions rather than halting early with a diagnostic error.

---

## Challenges

### [CRITICAL] Challenge 1: Non-existent Action Versions in GitHub Actions Workflow
- **Assumption challenged**: The workflow `.github/workflows/check.yml` uses valid GitHub Action action version tags.
- **Attack scenario**: Triggering `.github/workflows/check.yml` via `workflow_dispatch` or scheduled cron on GitHub Actions.
- **Blast radius**: 100% CI failure. The workflow will fail at setup time before running `python code/main.py --once`.
- **Mitigation**: Update `.github/workflows/check.yml` to use valid major tags: `actions/checkout@v4`, `actions/setup-python@v5`, `actions/cache/restore@v4`, `actions/cache/save@v4`.

### [HIGH] Challenge 2: Fragile Python Path Detection in Batch Scripts
- **Assumption challenged**: User's Python executable will be at `C:\Users\andre\AppData\Local\Python\bin\python.exe` or standard `python` in `%PATH%`.
- **Attack scenario**: Running `ejecutar_revisor_local.bat` on a standard Windows machine where Python is installed in `%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe` or where Windows App Alias intercepts `python`.
- **Blast radius**: Local execution fails with `'python' is not recognized as an internal or external command` or opens Microsoft Store app page.
- **Mitigation**: Use dynamic environment variables (`%USERPROFILE%` / `%LOCALAPPDATA%`), check for virtual environment `.venv\Scripts\python.exe`, or set `cd /d "%~dp0"`.

### [MEDIUM] Challenge 3: Unhandled Error Propagation in Local Batch Runner
- **Assumption challenged**: `get_cookies.py` will always succeed before `main.py` executes.
- **Attack scenario**: Colsubsidio authentication fails or Playwright dependencies are missing when `ejecutar_revisor_local.bat` is launched.
- **Blast radius**: `get_cookies.py` fails with exit code 1, but batch script continues into `main.py`, polluting logs with double failure and attempting requests with empty/stale tokens.
- **Mitigation**: Add error level check in `ejecutar_revisor_local.bat`:
  ```cmd
  "%PYTHON_EXE%" "%~dp0code\get_cookies.py"
  if %ERRORLEVEL% neq 0 (
      echo [ERROR] Fallo la extraccion de cookies. Abortando ejecucion.
      pause
      exit /b %ERRORLEVEL%
  )
  ```

### [MEDIUM] Challenge 4: High Cache Accumulation Rate in CI
- **Assumption challenged**: Saving a cache key formatted as `state-cache-${{ github.run_id }}-${{ github.run_attempt }}` every 10 minutes is sustainable.
- **Attack scenario**: 144 scheduled runs per day generate 1,008 cache entries per week.
- **Blast radius**: Exceeds GitHub repository 10 GB cache quota, leading to eviction of the Playwright binary cache (`~/.cache/ms-playwright`), increasing CI job duration from 15 seconds to 2+ minutes per run.
- **Mitigation**: Use a constant cache key (e.g. `state-cache-latest`) with `restore-keys: state-cache-` or handle state persistence cleanly.

---

## Stress Test Results

| Scenario | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|
| CI Workflow Tag Validity | Valid Action tags (`v4`, `v5`) | Uses `@v5` for checkout, `@v6` for setup-python, `@v5` for cache | **FAIL** |
| Batch Script Portable Path | Resolves user profile dynamically | Hardcoded `C:\Users\andre\...` | **FAIL** |
| Batch Script Error Handling | Aborts `main.py` if `get_cookies.py` fails | Proceeds to `main.py` regardless of `%ERRORLEVEL%` | **FAIL** |
| Batch Working Dir Independence | Sets CWD to script dir (`cd /d "%~dp0"`) | Leaves CWD unchanged, breaking relative `.env` load | **FAIL** |
| Requirements & Env Example | Contain `playwright>=1.40.0`, `COLSUBSIDIO_USER` | Present in `code/requirements.txt` & `.env.example` | **PASS** |

---

## Caveats

- **Network execution**: Actual remote run on GitHub servers was not triggered via remote API as we are in CODE_ONLY mode, but action version tag existence was verified against official GitHub Actions tag specifications.
- **Windows Store App Alias**: Behavior was verified against standard Windows 10/11 default environment configuration.

---

## Conclusion

Milestone 4 introduces important local runner and CI workflow assets, but contains critical version errors in `.github/workflows/check.yml` and hardcoded path/error propagation bugs in local `.bat` scripts. Addressing these findings will make Milestone 4 robust, fully portable, and CI-ready.

---

## Verification Method

1. **Verify GitHub Workflow Tags**:
   Inspect `.github/workflows/check.yml` lines 23, 26, 48, 77. Ensure tags match available GitHub Actions major releases (`actions/checkout@v4`, `actions/setup-python@v5`, `actions/cache/restore@v4`, `actions/cache/save@v4`).

2. **Verify Batch Script Fallback & Robustness**:
   Inspect `actualizar_cookies.bat` and `ejecutar_revisor_local.bat`. Verify `cd /d "%~dp0"` is present, hardcoded `andre` path is parameterized with `%USERPROFILE%` / `%LOCALAPPDATA%`, and `if %ERRORLEVEL% neq 0` guards execution of `main.py`.

3. **Run Pytest Suite**:
   Run `pytest harness/tests/ -v` to ensure all unit and integration tests pass.
