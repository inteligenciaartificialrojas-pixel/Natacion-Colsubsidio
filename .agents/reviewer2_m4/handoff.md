# Milestone 4 Handoff & Review Report — CI/CD & Local Runner Compatibility

## Review Summary

**Verdict**: REQUEST_CHANGES

The work for Milestone 4 contains **Critical** workflow errors, **Major** security vulnerabilities (secret leakage in logs), and **Major** cross-platform batch runner defects that must be addressed prior to approval.

---

## 1. Observation

Direct observations from source code inspection:

### Observation 1.1: Broken/Non-existent GitHub Actions Versions in `.github/workflows/check.yml`
- **Location**: `.github/workflows/check.yml`, lines 23, 26, 48, 77.
- **Code snippet**:
  ```yaml
  23:     - name: Descargar Código
  24:       uses: actions/checkout@v5
  25: 
  26:     - name: Configurar Python
  27:       uses: actions/setup-python@v6
  ...
  48:     - name: Restaurar Caché de Estado
  49:       uses: actions/cache/restore@v5
  ...
  77:       uses: actions/cache/save@v5
  ```
- **Fact**: `actions/checkout@v5` and `actions/setup-python@v6` do not exist (latest stable major releases are `actions/checkout@v4` and `actions/setup-python@v5`). `actions/cache/restore@v5` and `actions/cache/save@v5` do not exist (latest stable major is `v4`).

### Observation 1.2: Plaintext Logging of Sensitive Session Cookies in `code/get_cookies.py`
- **Location**: `code/get_cookies.py`, lines 414–416.
- **Code snippet**:
  ```python
  414:         print("\n[RESULTADOS ENCONTRADOS]")
  415:         print(f"sistema: {cookies['sistema']}")
  416:         print(f"Csrf-Token: {cookies['Csrf-Token']}")
  ```
- **Fact**: `get_cookies.py` prints the raw `sistema` session cookie and `Csrf-Token` to standard output. When executed by local runners or CI scripts, sensitive credentials will be printed into execution logs.

### Observation 1.3: Hardcoded Specific User Path in Batch Scripts
- **Location**: `actualizar_cookies.bat` (lines 10–12) & `ejecutar_revisor_local.bat` (lines 11–13).
- **Code snippet**:
  ```bat
  10: set "PYTHON_EXE=python"
  11: if exist "C:\Users\andre\AppData\Local\Python\bin\python.exe" (
  12:     set "PYTHON_EXE=C:\Users\andre\AppData\Local\Python\bin\python.exe"
  13: )
  ```
- **Fact**: Hardcodes user-specific path `C:\Users\andre\...` for user `andre`.

### Observation 1.4: Aggressive Unwarned Process Termination
- **Location**: `code/get_cookies.py`, lines 407–409.
- **Code snippet**:
  ```python
  407:         import subprocess
  408:         subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  409:         subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  ```
- **Fact**: Executes `taskkill /F` against all Chrome and Edge processes when `main()` is run on Windows.

### Observation 1.5: Incomplete Test Assertions in `test_m4_cicd_local_runner.py`
- **Location**: `harness/tests/test_m4_cicd_local_runner.py`, lines 26–53.
- **Fact**: `test_github_workflow_check_yml_configuration` checks string inclusion of `"actions/cache"` and `"python code/main.py --once"`, but fails to test for valid GitHub Action release tags, masking the broken `@v5` / `@v6` action references.

---

## 2. Logic Chain

1. **Step 1 (CI/CD Execution Failure)**: In `.github/workflows/check.yml`, specifying `actions/checkout@v5` and `actions/setup-python@v6` causes GitHub Actions runners to attempt resolving non-existent Git tags/releases. This will cause any CI pipeline execution to fail immediately at step setup.
2. **Step 2 (Security Violation / Secret Leak)**: Requirement 1 demands verifying that secrets are not printed in logs. In `code/get_cookies.py`, printing `cookies['sistema']` and `cookies['Csrf-Token']` directly to `sys.stdout` violates secret masking standards, causing full session cookies to leak into runner logs.
3. **Step 3 (Runner Portability Defect)**: Requirement 3 demands cross-platform runner compatibility. Hardcoding `C:\Users\andre\...` inside `actualizar_cookies.bat` and `ejecutar_revisor_local.bat` ties execution to a specific local user directory on a single machine, breaking execution for other Windows users or standard environments where `%LOCALAPPDATA%` or `%USERPROFILE%` should be used.
4. **Step 4 (Side Effect Risk)**: Calling `taskkill /F /IM msedge.exe /IM chrome.exe` without prompt or confirmation forcibly terminates all active browser windows when running `get_cookies.py` on Windows, creating data loss risks for local users.
5. **Step 5 (Self-Certifying Test Failure)**: `test_m4_cicd_local_runner.py` asserts that `.github/workflows/check.yml` contains basic strings, but does not check if the referenced action versions exist or are valid, leading to false-pass confidence during testing.

---

## 3. Findings

### [Critical] Finding 1: Broken Action Versions in `.github/workflows/check.yml`
- **What**: `.github/workflows/check.yml` uses non-existent action versions `actions/checkout@v5`, `actions/setup-python@v6`, `actions/cache/restore@v5`, and `actions/cache/save@v5`.
- **Where**: `.github/workflows/check.yml:24,27,49,77`
- **Why**: GitHub Actions runner cannot resolve non-existent action release tags.
- **Suggestion**: Update `.github/workflows/check.yml` to use valid stable major releases:
  - `actions/checkout@v4`
  - `actions/setup-python@v5`
  - `actions/cache@v4` (or `actions/cache/restore@v4` and `actions/cache/save@v4`)

### [Major] Finding 2: Plaintext Logging of Sensitive Session Cookies
- **What**: `code/get_cookies.py` prints sensitive session cookies to `sys.stdout`.
- **Where**: `code/get_cookies.py:415-416`
- **Why**: Violates secret confidentiality requirements; leaks session cookies into CI/CD and terminal logs.
- **Suggestion**: Mask cookie values when logging (e.g. `sistema: [MASKED]` or `sistema: <len 120>`), or log only success/failure status.

### [Major] Finding 3: Hardcoded Developer Path in Local Runner Batch Scripts
- **What**: `actualizar_cookies.bat` and `ejecutar_revisor_local.bat` contain a hardcoded user path (`C:\Users\andre\...`).
- **Where**: `actualizar_cookies.bat:11`, `ejecutar_revisor_local.bat:12`
- **Why**: Hardcoding specific local user names breaks cross-platform and multi-user compatibility.
- **Suggestion**: Use environment variables, e.g.:
  ```bat
  if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
      set "PYTHON_EXE=%LOCALAPPDATA%\Python\bin\python.exe"
  )
  ```

### [Minor] Finding 4: Destructive Force-Kill of Browser Instances
- **What**: `code/get_cookies.py` unconditionally force-kills all `chrome.exe` and `msedge.exe` processes on Windows.
- **Where**: `code/get_cookies.py:408-409`
- **Why**: Unexpectedly closes user browser windows and causes work loss.
- **Suggestion**: Remove automatic `taskkill` or handle locked files gracefully (e.g. catch SQLite lock exceptions).

---

## 4. Caveats

- `run_command` timed out waiting for user approval on local terminal, so test evaluation was performed via direct code inspection and static analysis.
- Reviewer operated under strict read-only constraints; no implementation code was altered.

---

## 5. Conclusion

**Verdict**: **REQUEST_CHANGES**

Milestone 4 cannot be approved until:
1. Action version tags in `.github/workflows/check.yml` are fixed to valid existing releases (`checkout@v4`, `setup-python@v5`, `cache@v4`).
2. Plaintext printing of `sistema` and `Csrf-Token` in `code/get_cookies.py` is removed/masked.
3. Hardcoded user path `C:\Users\andre\...` in batch scripts is replaced with `%LOCALAPPDATA%\Python\bin\python.exe`.
4. Tests in `test_m4_cicd_local_runner.py` are updated to validate workflow action version references.

---

## 6. Verification Method

To independently verify after changes:
1. Inspect `.github/workflows/check.yml` to confirm action tags are `@v4` for checkout and `@v5` for setup-python.
2. Inspect `code/get_cookies.py` lines 414-416 to verify raw cookies are not printed to `stdout`.
3. Inspect `actualizar_cookies.bat` and `ejecutar_revisor_local.bat` to confirm `C:\Users\andre` is removed in favor of `%LOCALAPPDATA%`.
4. Run `pytest harness/tests/test_m4_cicd_local_runner.py -v`.
