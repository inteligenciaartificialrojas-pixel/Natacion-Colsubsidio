# Technical Analysis: CI/CD, Playwright Dependencies & Local Runner Setup

## 1. Executive Summary

This report presents a comprehensive technical analysis of the CI/CD workflow (`.github/workflows/check.yml`), Python dependencies (`code/requirements.txt`), environment configurations (`.env.example`), local batch scripts (`actualizar_cookies.bat`, `ejecutar_revisor_local.bat`), and test harness (`harness/`) for the Colsubsidio Swimming Availability Self-Healing project.

The current implementation relies on a legacy Windows DPAPI script (`code/get_cookies.py`) that extracts session cookies from local Chrome/Edge browser SQLite databases. This approach fails completely in headless CI/CD environments (Linux GitHub Actions runners) when session cookies expire, causing scheduled workflow runs to fail with exit code 1.

Migrating session renewal to Playwright headless Chromium enables automated, cross-platform login and cookie retrieval across both local Windows runners and GitHub Actions.

---

## 2. Current Architecture & Bottlenecks

### 2.1 GitHub Actions Workflow (`.github/workflows/check.yml`)
- **Current State**: Uses `ubuntu-latest` runner, sets up Python 3.11, installs `code/requirements.txt`, restores `.cooldown_state` / `.last_slots.json` cache, and executes `python code/main.py --once`.
- **Bottlenecks**:
  1. `code/requirements.txt` does not include `playwright`.
  2. Workflow does not execute `playwright install --with-deps chromium`. Without `--with-deps`, headless Chromium fails on Linux due to missing shared libraries (e.g., `libnss3`, `libgbm1`, `libasound2`).
  3. Environment variables passed to the job only include static cookie secrets (`COLSUBSIDIO_SISTEMA_COOKIE`, `COLSUBSIDIO_CSRF_TOKEN`), omitting login credentials (`COLSUBSIDIO_USER`, `COLSUBSIDIO_PASS`).
  4. When session cookies expire, `main.py` triggers `SessionExpiredException`. Because auto-healing in `main.py` was guarded by `if sys.platform == "win32"`, the Linux runner immediately aborts with exit code 1.

### 2.2 Legacy Cookie Extraction (`code/get_cookies.py`)
- Uses Windows `crypt32.dll` DPAPI decryption and searches Chrome/Edge user profile paths (`LOCALAPPDATA`).
- Incompatible with Linux CI/CD environments.
- High risk of database locking errors (`PermissionError`) if local browser is running.

### 2.3 Local Batch Scripts
- `actualizar_cookies.bat`: Hardcodes local user Python path `C:\Users\andre\AppData\Local\Python\bin\python.exe` with fallback to `python`. Invokes `code/get_cookies.py`.
- `ejecutar_revisor_local.bat`: Invokes `code/get_cookies.py` followed by `code/main.py`.

---

## 3. Playwright Dependency Requirements

To support automated headless login, the project requires:

1. **Python Package (`code/requirements.txt`)**:
   - `playwright>=1.40.0`
   - `requests>=2.31.0` (existing)
   - `pytest>=7.4.0` (existing)

2. **Browser Binary**:
   - Chromium headless browser binary (`python -m playwright install chromium`).

3. **Linux System Libraries (GitHub Actions `ubuntu-latest`)**:
   - Installed via `python -m playwright install --with-deps chromium`.

---

## 4. GitHub Actions Workflow Refactoring Plan

### 4.1 Required Changes in `.github/workflows/check.yml`

1. **Update Dependency Installation Step**:
   Replace:
   ```yaml
   - name: Instalar Dependencias
     run: |
       python -m pip install --upgrade pip
       pip install -r code/requirements.txt
   ```
   With:
   ```yaml
   - name: Instalar Dependencias y Playwright Chromium
     run: |
       python -m pip install --upgrade pip
       pip install -r code/requirements.txt
       python -m playwright install --with-deps chromium
   ```

2. **Add Playwright Browser Caching (Performance Optimization)**:
   Add an `actions/cache` step to cache `~/.cache/ms-playwright`:
   ```yaml
   - name: Cache Playwright Browsers
     uses: actions/cache@v5
     with:
       path: ~/.cache/ms-playwright
       key: ${{ runner.os }}-playwright-${{ hashFiles('code/requirements.txt') }}
       restore-keys: |
         ${{ runner.os }}-playwright-
   ```

3. **Pass Login Credentials Secrets**:
   Add `COLSUBSIDIO_USER` and `COLSUBSIDIO_PASS` to `env` block in `Ejecutar Revisor` step:
   ```yaml
   COLSUBSIDIO_USER: ${{ secrets.COLSUBSIDIO_USER }}
   COLSUBSIDIO_PASS: ${{ secrets.COLSUBSIDIO_PASS }}
   ```

---

## 5. Local Runner & Batch Script Compatibility

### 5.1 Batch Script Updates (`actualizar_cookies.bat` & `ejecutar_revisor_local.bat`)
- Retain flexible Python executable discovery (`PYTHON_EXE`).
- When `get_cookies.py` is updated to Playwright, running `actualizar_cookies.bat` or `ejecutar_revisor_local.bat` will trigger Playwright headless (or headful) login without requiring Chrome/Edge process termination (`taskkill`).
- Graceful error handling: If `playwright` is not installed locally, output a clean user prompt directing the user to run `pip install playwright && playwright install chromium`.

---

## 6. Environment Configuration (`.env.example`) Updates

`.env.example` should be updated to include credential placeholders required for automated Playwright login:

```env
# --- COLSUBSIDIO LOGIN CREDENTIALS (For Playwright Automated Self-Healing) ---
# Document number or username for Colsubsidio account login
COLSUBSIDIO_USER=tu_usuario_o_documento_aqui

# Account password for Colsubsidio login
COLSUBSIDIO_PASS=tu_contrasena_aqui

# Document type (e.g., CC, CE, PASAPORTE)
COLSUBSIDIO_DOCUMENT_TYPE=CC
COLSUBSIDIO_DOCUMENT_NUMBER=tu_numero_documento_aqui
```

---

## 7. Test Harness & Quality Control (`harness/`)

1. **Unit Test Coverage (`harness/tests/`)**:
   - Add unit tests for `get_cookies.py` Playwright helper under `harness/tests/test_get_cookies.py`.
   - Mock Playwright page interaction (`sync_playwright`) in pytest using `unittest.mock` to ensure unit tests execute fast without actual network traffic.
2. **Environment Health Check (`harness/init.ps1` & `harness/init.sh`)**:
   - The initialization scripts check `python -m pytest tests/` and validate `code/requirements.txt`.
   - `init.ps1` and `init.sh` remain fully compatible.
