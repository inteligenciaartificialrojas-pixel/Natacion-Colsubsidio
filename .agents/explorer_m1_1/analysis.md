# Comprehensive Investigation Report: Authentication & Cookie Management

## 1. Executive Summary

This report presents the findings of the investigation conducted by **Explorer 1** for **Milestone 1** of the *Colsubsidio Swimming Availability Self-Healing* project. 

The primary goal of this investigation is to evaluate the existing cookie extraction and authentication mechanisms, analyze the login flow for `diversioncolsubsidio.com`, and design a headless Playwright-based automated login solution that operates seamlessly across local (Windows) and CI/CD (Linux/GitHub Actions) environments.

---

## 2. Analysis of Existing Codebase & Cookie Management

### 2.1 File Analysis Overview

| File Path | Current Functionality | Key Findings & Limitations |
|-----------|------------------------|----------------------------|
| `code/get_cookies.py` | Extracts `sistema` and `Csrf-Token` cookies from local Chrome/Edge SQLite databases in Windows. | **Windows DPAPI lock-in**: Uses `ctypes.windll.crypt32.CryptUnprotectData` to decrypt browser keys. Requires user to manually open browser and log in first. Kills browser processes (`taskkill`). Fails completely on Linux CI/CD runners. |
| `code/config.py` | Parses `.env` key-value pairs without external dependencies (`python-dotenv`). Loads `COLSUBSIDIO_SISTEMA_COOKIE`, `COLSUBSIDIO_CSRF_TOKEN`, etc. | Lacks environment definitions for `COLSUBSIDIO_USER` and `COLSUBSIDIO_PASS`. Needs extension to support credential-driven automated login. |
| `.env` / `.env.example` | Environment configuration files storing Telegram tokens and Colsubsidio cookies (`COLSUBSIDIO_SISTEMA_COOKIE`, `COLSUBSIDIO_CSRF_TOKEN`). | Currently missing placeholders/keys for `COLSUBSIDIO_USER` and `COLSUBSIDIO_PASS`. |
| `actualizar_cookies.bat` | Windows batch script calling `python code/get_cookies.py`. | Contains hardcoded path to Python executable (`C:\Users\andre\AppData\Local\Python\bin\python.exe`). Relies on legacy extractor. |
| `code/scraper.py` | Performs HTTP requests to Colsubsidio API (`/v1/centro_entrenamiento/...`) using `requests.Session`. | Raises `SessionExpiredException` on HTTP 401, JSON `"status": "Unauthorized"`, or HTML redirect to `loguearSitio`. Prepared for self-healing hook. |
| `code/main.py` | Main CLI orchestration loop. Catches `SessionExpiredException`. | Currently calls `get_cookies.extract_colsubsidio_cookies()` on Windows only, falling back to Telegram alert if extraction fails. Needs integration with Playwright auto-login. |
| `code/requirements.txt` | Lists project dependencies (`requests>=2.31.0`, `pytest>=7.4.0`). | **Missing Playwright dependency**: `playwright` is not yet installed or listed in `requirements.txt`. |
| `.github/workflows/check.yml` | GitHub Actions workflow executing scraper every 10 minutes on `ubuntu-latest`. | Passes `COLSUBSIDIO_SISTEMA_COOKIE` and `COLSUBSIDIO_CSRF_TOKEN` from secrets. Lacks browser setup steps (`playwright install chromium`). |

---

## 3. Colsubsidio Login Portal & Cookie Architecture

### 3.1 Login URL & Flow Analysis
- **Login Portal URL**: `https://www.diversioncolsubsidio.com/sistema.php/default/loguearSitio`
- **Session Identification Cookies**:
  - `sistema`: PHP session cookie identifying authenticated user session state.
  - `Csrf-Token`: Security token required for state-changing requests and API calls.
  - `sitio`: Secondary session mirror cookie set by backend.
- **Form Elements & DOM Structure**:
  - Document Type selector: `#tipo_documento` or `select[name="tipo_documento"]` (Values: `CC` - Cédula de Ciudadanía, `CE`, `TI`, `PAS`).
  - Document / Username input field: `#documento` or `input[name="documento"]` / `input[name="usuario"]`.
  - Password input field: `#clave` or `input[name="clave"]` / `input[type="password"]`.
  - Submit action: Form submit button `#btn-ingresar` or `button[type="submit"]`.

### 3.2 Key Differences: DPAPI vs Playwright Headless Login

| Feature / Metric | Existing DPAPI Extraction (`get_cookies.py`) | Proposed Playwright Automation |
|------------------|---------------------------------------------|--------------------------------|
| **Execution Trigger** | Manual pre-requisite (user logs in via Chrome/Edge) | Automated on-demand or background self-healing |
| **OS Compatibility** | Windows OS only (`win32`) | Cross-platform (Windows, Linux, macOS) |
| **CI/CD Capability** | Incompatible with GitHub Actions (Linux runner) | 100% Compatible with GitHub Actions |
| **Process Interruption** | Kills user browser (`taskkill msedge.exe`) | Isolated headless Chromium instance |
| **Maintenance** | Fragile (Chrome/Edge DPAPI changes) | Stable (Standard web browser DOM interaction) |

---

## 4. Proposed Playwright Automated Login Design

### 4.1 Interface Contract
The automated login function in `code/get_cookies.py` will expose the following interface as specified in `PROJECT.md`:

```python
def login_and_get_cookies(
    user: str | None = None,
    password: str | None = None,
    doc_type: str = "CC"
) -> dict[str, str]:
    """
    Automates headless Chromium login to Colsubsidio portal using Playwright.
    
    Args:
        user: Document number or username (defaults to COLSUBSIDIO_USER or COLSUBSIDIO_DOCUMENT_NUMBER env var).
        password: Colsubsidio password (defaults to COLSUBSIDIO_PASS env var).
        doc_type: Document type (defaults to COLSUBSIDIO_DOCUMENT_TYPE env var or "CC").
        
    Returns:
        dict containing extracted 'sistema' and 'Csrf-Token' cookies.
    """
```

### 4.2 Playwright Automation Workflow Sequence

1. **Environment & Credential Check**:
   - Retrieve credentials from parameters or `os.environ`:
     - `COLSUBSIDIO_USER` / `COLSUBSIDIO_DOCUMENT_NUMBER`
     - `COLSUBSIDIO_PASS`
     - `COLSUBSIDIO_DOCUMENT_TYPE`
   - If `user` or `password` is missing, log an error and return empty dict or fallback to DPAPI if on Windows.

2. **Playwright Execution**:
   - Initialize `sync_playwright()`.
   - Launch Chromium browser in headless mode: `browser = p.chromium.launch(headless=True)`.
   - Create fresh context: `context = browser.new_context(user_agent="...")`.
   - Create new page and navigate: `page.goto("https://www.diversioncolsubsidio.com/sistema.php/default/loguearSitio")`.

3. **Form Interaction & Submission**:
   - Wait for form selectors (`page.wait_for_selector(...)`).
   - Fill document type dropdown (if present): `page.select_option("select[name='tipo_documento']", doc_type)`.
   - Fill document number: `page.fill("input[name='documento']", user)`.
   - Fill password: `page.fill("input[name='clave']", password)`.
   - Click submit button: `page.click("button[type='submit']")` or `#btn-ingresar`.
   - Wait for redirection / network idle state: `page.wait_for_load_state("networkidle")`.

4. **Cookie Extraction & Persistence**:
   - Extract cookies from browser context: `context_cookies = context.cookies()`.
   - Parse target cookie values (`sistema` and `Csrf-Token`).
   - Persist to `.env` using existing `update_env_file(cookies)` logic.
   - Sync with GitHub Secrets via `sync_secrets_to_github(cookies)` if `gh` CLI is available.
   - Close browser and return cookies dictionary `{"sistema": "...", "Csrf-Token": "..."}`.

---

## 5. Environment Verification & Dependencies Audit

1. **Python Environment**:
   - Detected Python version: `3.14.6` on Windows (`win32`).
2. **Missing Dependencies**:
   - `playwright` is currently **not installed** in the environment.
   - `code/requirements.txt` must be updated to include `playwright>=1.40.0`.
   - Post-install script required: `playwright install chromium`.

---

## 6. Recommendations for Milestone 2 (Implementation)

1. **Update Environment Files**: Add `COLSUBSIDIO_USER` and `COLSUBSIDIO_PASS` to `.env.example` and `config.py`.
2. **Implement `login_and_get_cookies()`**: In `code/get_cookies.py`, provide the Playwright login helper with fallback to DPAPI on Windows if credentials are not provided.
3. **CI/CD Workflow Readiness**: Update `.github/workflows/check.yml` to install `playwright` and Chromium browser dependencies.
