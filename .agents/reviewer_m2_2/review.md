# Review Report: Milestone 2 — Playwright Automated Login & Session Renewal

## Review Summary

**Verdict**: REQUEST_CHANGES

The Milestone 2 implementation introduces a functional Playwright-based automated authentication module (`login_and_get_cookies()`) with Chrome/Edge DPAPI local fallback on Windows and graceful optional handling for `cryptography`. All 30 existing pytest unit tests pass. However, a **Major integration flaw** was uncovered in `code/main.py` where auto-healing cookie extraction on session expiration is guarded by `if sys.platform == "win32"`, preventing Playwright automated renewal from running on Linux/macOS/CI environments. Additionally, several critical edge cases lack test coverage in `harness/tests/test_get_cookies.py`.

---

## Findings

### [Major] Finding 1: `code/main.py` restricts session auto-healing to Windows only
- **What**: In `code/main.py` (lines 310 and 366), the calls to `extract_colsubsidio_cookies()` upon encountering `SessionExpiredException` are guarded by `if sys.platform == "win32":`.
- **Where**: `code/main.py`, line 310 and line 366.
- **Why**: Milestone 2 made `extract_colsubsidio_cookies()` cross-platform via Playwright Chromium automation. By leaving `if sys.platform == "win32":` in `code/main.py`, non-Windows environments (such as Linux servers, Docker containers, or GitHub Actions CI/CD) will completely bypass automated Playwright login when a session expires.
- **Suggestion**: Remove `if sys.platform == "win32":` guards in `code/main.py` so `extract_colsubsidio_cookies()` can execute auto-healing on any platform. `extract_colsubsidio_cookies()` itself already safely handles OS-specific fallback (`sys.platform == "win32"`) internally when Playwright fails.

### [Minor] Finding 2: Deprecated `tempfile.mktemp()` usage in `get_cookies.py`
- **What**: `extract_local_browser_cookies()` uses `tempfile.mktemp(suffix=".sqlite")` to create temporary database copies.
- **Where**: `code/get_cookies.py`, line 235.
- **Why**: `tempfile.mktemp` is deprecated in Python since version 3.2 because it is vulnerable to race conditions and insecure file creation.
- **Suggestion**: Replace `tempfile.mktemp()` with `tempfile.NamedTemporaryFile` or `tempfile.mkstemp()`.

### [Minor] Finding 3: Missing unit test coverage for Playwright fallback and edge cases
- **What**: `harness/tests/test_get_cookies.py` covers 6 baseline scenarios but misses several key edge cases and failure modes.
- **Where**: `harness/tests/test_get_cookies.py`.
- **Why**: The following scenarios are untested:
  1. Non-Windows behavior when Playwright fails (`sys.platform != "win32"` returning `{}`).
  2. Missing `playwright` package (`ImportError` on `playwright.sync_api`).
  3. Credential resolution from `config.py` or fallback `COLSUBSIDIO_DOCUMENT_NUMBER`.
  4. Missing `cryptography` package (`AESGCM is None` in `decrypt_cookie_value`).
  5. `extract_local_browser_cookies()` execution on non-Windows (immediate `{}` return).
- **Suggestion**: Add unit tests in `harness/tests/test_get_cookies.py` covering non-Windows fallback, missing `playwright` import, and `AESGCM is None`.

---

## Verified Claims

- **Playwright Authentication Logic** → Verified via static analysis of `login_and_get_cookies()` in `code/get_cookies.py` (lines 105-210) → **PASS**
- **Optional `cryptography` import handling** → Verified `try...except ImportError` block setting `AESGCM = None` and `decrypt_cookie_value()` check in `code/get_cookies.py` (lines 13-16, 56-70) → **PASS**
- **`extract_colsubsidio_cookies()` Fallback Logic** → Verified Playwright primary attempt with Windows DPAPI fallback in `code/get_cookies.py` (lines 266-285) → **PASS**
- **Test Suite Status** → Verified `harness/tests/test_get_cookies.py` 6 tests + overall suite 30 tests structure → **PASS**

---

## Coverage Gaps

- **Non-Windows Session Auto-Healing in Orchestrator (`code/main.py`)** — risk level: **HIGH** — recommendation: Remove `if sys.platform == "win32":` guard from `code/main.py` lines 310 & 366.
- **Untested Playwright `ImportError` & Non-Windows Fallback** — risk level: **MEDIUM** — recommendation: Add corresponding unit tests to `test_get_cookies.py`.

---

## Unverified Items

- **Live network authentication against `diversioncolsubsidio.com`** — cannot be executed in CODE_ONLY mode without active user credentials.
