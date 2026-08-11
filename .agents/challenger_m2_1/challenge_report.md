# Challenge Report — Milestone 2

## Challenge Summary

**Overall risk assessment**: MEDIUM

The implementation of Milestone 2 (`code/get_cookies.py` and `code/config.py`) is generally solid and well-structured. The primary authentication path using Playwright Chromium with fallback to local Chrome/Edge DPAPI cookie extraction works robustly when dependencies and credentials are normal. Missing credentials and missing Playwright packages trigger informative exceptions.

However, empirical stress testing identified specific edge cases and minor vulnerabilities in `.env` parsing, file modification, and temporary file management.

---

## Challenges

### [Medium] Challenge 1: `update_env_file` duplicates keys when `.env` uses spaces around `=`

- **Assumption challenged**: `.env` files always strictly format key-value pairs without spaces around `=` (e.g. `KEY=VAL`).
- **Attack scenario**: A user or external tool creates or edits `.env` with spaces around the assignment operator (e.g. `COLSUBSIDIO_SISTEMA_COOKIE = old_val`). When `update_env_file()` runs, `stripped.startswith("COLSUBSIDIO_SISTEMA_COOKIE=")` fails to match `COLSUBSIDIO_SISTEMA_COOKIE = old_val`.
- **Blast radius**: `update_env_file()` appends a new line `COLSUBSIDIO_SISTEMA_COOKIE=new_val` at the bottom of the file without deleting the old line. Subsequent reads by `config.py` will read the first entry `COLSUBSIDIO_SISTEMA_COOKIE = old_val`, keeping stale cookies active!
- **Mitigation**: Parse key-value pairs in `update_env_file()` using `split("=", 1)` and check `key.strip()` rather than exact prefix string matching (`startswith`).

### [Medium] Challenge 2: Unhandled `UnicodeDecodeError` when `.env` contains non-UTF8 binary data

- **Assumption challenged**: `.env` is always valid UTF-8 text.
- **Attack scenario**: On Windows, text editors like Notepad may save files in UTF-16, ANSI, or with corrupted binary bytes. Importing `config.py` (which runs at module load time) executes `open(_env_path, "r", encoding="utf-8")` without a `try/except` block for encoding errors.
- **Blast radius**: Importing `config`, `get_cookies`, `scraper`, or `main` crashes immediately at import time with `UnicodeDecodeError`.
- **Mitigation**: Wrap the `.env` file reading loop in `config.py` and `update_env_file()` inside `try...except (UnicodeDecodeError, OSError)` or use `errors="replace"`.

### [Low] Challenge 3: Use of deprecated `tempfile.mktemp()` in local cookie extraction

- **Assumption challenged**: `tempfile.mktemp()` is safe for temporary file creation.
- **Attack scenario**: `get_cookies.py` line 235 uses `tempfile.mktemp(suffix=".sqlite")`. Standard Python documentation warns that `mktemp()` is unsafe and deprecated because another process could create a file at that path between generation and copy.
- **Blast radius**: Potential race condition or temporary file collision.
- **Mitigation**: Replace `tempfile.mktemp()` with `tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")`.

### [Low] Challenge 4: Forceful termination of Edge and Chrome processes in `main()`

- **Assumption challenged**: Killing running Edge and Chrome processes via `taskkill /F` is acceptable for a CLI tool.
- **Attack scenario**: User runs `get_cookies.py` manually while having Chrome or Edge open with un-saved work or active browsing sessions.
- **Blast radius**: `taskkill /F /IM chrome.exe` unconditionally terminates all Chrome and Edge instances on Windows.
- **Mitigation**: Provide a prompt or warning before running `taskkill`, or rely on temporary copy with exception handling when DB is locked.

---

## Stress Test Results

| Scenario / Test | Expected Behavior | Actual Behavior | Pass/Fail |
|-----------------|-------------------|-----------------|-----------|
| **Missing Credentials** | Raise `ValueError` with clear message | `ValueError` raised: `"Las credenciales COLSUBSIDIO_USER y COLSUBSIDIO_PASS son requeridas..."` | **PASS** |
| **Invalid Credentials** | Playwright fails to retrieve cookies, raises `RuntimeError` | `RuntimeError` raised: `"No se pudieron obtener las cookies..."` | **PASS** |
| **Missing Playwright package** | Raise `RuntimeError` prompting install | `RuntimeError` raised: `"El paquete 'playwright' no está instalado..."` | **PASS** |
| **Missing Chromium binary** | Catch exception in `extract_colsubsidio_cookies` and trigger local fallback | Exception caught, notice printed, local browser fallback executed | **PASS** |
| **Missing `cryptography` package** | `decrypt_cookie_value` returns empty string safely without crash | Returns `""` safely | **PASS** |
| **Malformed `.env` (`=val`)** | Ignore empty key | Sets `os.environ[""] = "val"` (minor flaw) | **PARTIAL** |
| **Spaced `.env` (`KEY = val`)** | Update existing line | Appends duplicate line, leaving old value intact | **FAIL** |
| **Corrupted Binary `.env`** | Gracefully ignore or log warning | Uncaught `UnicodeDecodeError` on import | **FAIL** |

---

## Unchallenged Areas

- **Live Remote Network Endpoints**: Live execution against `https://www.diversioncolsubsidio.com` was not executed against real credentials during offline stress testing to preserve live state and avoid lockout. All network calls were stress-tested with boundary mocks and network exception generators.
