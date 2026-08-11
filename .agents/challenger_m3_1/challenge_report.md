# Challenge Report — Milestone 3 Self-Healing Logic Audit

## Challenge Summary

**Overall risk assessment**: **HIGH**

The self-healing logic in `code/scraper.py` succeeds in basic HTTP 401 retry recovery, but contains significant failure modes and unhandled edge cases under adversarial conditions:
1. **Persistent HTTP 401 & Contract Violations**: `book_slot` raises uncaught `SessionExpiredException` instead of returning `(False, msg)`, causing main loop crashes during Telegram interactive bookings. Additionally, double renewal triggers occur between `scraper.py` and `main.py`.
2. **Unexpected / Malformed JSON Bodies**: API responses returning JSON lists (`[]`), null values (`{"fechas": null}`), or non-dictionary elements crash `fetch_available_dates` and `fetch_slots_for_date` with unhandled `AttributeError`. Furthermore, `_check_unauthorized` only detects `data.get("status") == "Unauthorized"`, ignoring alternative error keys like `{"error": "Unauthorized"}` or `{"status": 401}`.
3. **Network & Subprocess Errors during Session Renewal**: Non-`requests` exceptions (e.g. Playwright `RuntimeError`, `Error`, `TimeoutError`) thrown during `extract_colsubsidio_cookies()` crash `fetch_available_dates` and `fetch_slots_for_date` without graceful handling.
4. **Concurrent Renewal Stampede & Race Conditions**: Simultaneous 401 responses across concurrent requests trigger multiple parallel Playwright browser instances without mutex/locking, resulting in redundant extractions and file write contention on `.env`.

---

## Challenges

### [High] Challenge 1: `book_slot` Breaks Return Contract on Persistent 401 & Crashes Telegram Command Handler

- **Assumption challenged**: `book_slot` always returns a `tuple[bool, str]` contract (`(False, error_msg)` or `(True, success_msg)`).
- **Attack scenario**: User issues `/agendar` via Telegram when the Colsubsidio session is expired and session renewal fails or persistent 401 is returned. `_execute_with_retry` exhausts retries and re-raises `SessionExpiredException`. Line 340 of `code/scraper.py` explicitly re-raises `SessionExpiredException`.
- **Blast radius**: `main.py` lines 263-279 call `scraper.book_slot()` without a `try...except SessionExpiredException` block. The entire application crashes with an unhandled exception instead of notifying the user of booking failure on Telegram.
- **Mitigation**: Update `book_slot` to catch `SessionExpiredException` and return `(False, "La sesión expiró y no se pudo renovar automáticamente.")`, or wrap `scraper.book_slot()` calls in `main.py` with `try...except SessionExpiredException`.

---

### [High] Challenge 2: Unhandled `AttributeError` Crashes on Malformed or List JSON Bodies

- **Assumption challenged**: Colsubsidio API always returns a JSON dictionary containing a `"fechas"` or `"horarios"` dictionary/list.
- **Attack scenario**: API returns HTTP 200 with a JSON list `[{"error": "invalid"}]`, `[]`, or `{"fechas": null}`.
- **Blast radius**:
  - `fetch_available_dates`: `data = response.json()` -> `data.get("fechas", {})` raises `AttributeError: 'list' object has no attribute 'get'`.
  - Line 154 only catches `ValueError`. The `AttributeError` is uncaught and crashes the scraper execution.
  - `fetch_slots_for_date`: Same crash behavior on `data.get("horarios", [])`.
- **Mitigation**: Add defensive type checking (`isinstance(data, dict)`) before calling `.get()`, and expand exception handlers to catch `(ValueError, AttributeError, TypeError)`.

---

### [Medium] Challenge 3: Incomplete Unauthorized Detection in `_check_unauthorized`

- **Assumption challenged**: Colsubsidio API unauthorized responses always use `status_code == 401` or JSON payload `{"status": "Unauthorized"}`.
- **Attack scenario**: API returns HTTP 200 with JSON body `{"error": "Unauthorized"}`, `{"status": 401}`, `{"code": "UNAUTHORIZED"}`, or `{"message": "jwt expired"}`.
- **Blast radius**: `_check_unauthorized` ignores these error structures and returns cleanly. Self-healing session renewal is NOT triggered. The scraper treats the response as valid, returning `[]` available dates/slots without attempting self-healing.
- **Mitigation**: Enhance `_check_unauthorized` to inspect `error`, `code`, `message`, `status`, and integer status values for unauthorized signatures (e.g. `"unauthorized" in str(data).lower()` or checking keys `error`, `status`, `code`).

---

### [Medium] Challenge 4: Unhandled Non-`requests` Exceptions during Session Renewal

- **Assumption challenged**: `extract_colsubsidio_cookies()` only raises `requests.RequestException`.
- **Attack scenario**: `extract_colsubsidio_cookies()` fails due to missing Playwright executable, browser crash, OS process error, or DOM timeout (`RuntimeError`, `TargetClosedError`, `TimeoutError`).
- **Blast radius**: `_renew_session` does not catch these exceptions. `fetch_available_dates` and `fetch_slots_for_date` only catch `except requests.RequestException:`. The non-`requests` exception propagates up, crashing `main.py`.
- **Mitigation**: Wrap `extract_colsubsidio_cookies()` in `_renew_session` with `try...except Exception as e:` and raise `SessionExpiredException(f"Error durante renovación: {e}")`.

---

### [Medium] Challenge 5: Race Condition & Thundering Herd on Concurrent 401 Session Renewal

- **Assumption challenged**: Session renewal requests occur strictly single-threaded and sequentially.
- **Attack scenario**: Multiple requests (e.g., scanning multiple venues in parallel threads or concurrent trigger) hit 401 simultaneously.
- **Blast radius**: All threads enter `_renew_session()` concurrently. Multiple Playwright browser processes launch simultaneously. `update_env_file()` is called concurrently, causing race conditions and disk write locks on `.env` (Windows file lock errors).
- **Mitigation**: Implement a `threading.Lock()` inside `ColsubsidioScraper` / `_renew_session()` so that only one thread performs session renewal while other waiting threads reuse the newly updated credentials.

---

## Stress Test Results

| Scenario | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|
| Single 401 auto-retry recovery | Refresh session, retry request, return data | Session refreshed and retry succeeds | **PASS** |
| Persistent 401 in `fetch_available_dates` | Raise `SessionExpiredException` after 1 retry | Raises `SessionExpiredException` after 1 retry | **PASS** |
| Persistent 401 in `book_slot` | Return `(False, error_msg)` | Raises uncaught `SessionExpiredException` | **FAIL** |
| HTTP 200 with JSON list `[]` | Return `[]` gracefully | Crashes with unhandled `AttributeError` | **FAIL** |
| HTTP 200 with `{"fechas": null}` | Return `[]` gracefully | Crashes with unhandled `AttributeError` | **FAIL** |
| HTTP 200 with `{"error": "Unauthorized"}` | Trigger `SessionExpiredException` and self-heal | Missed unauthorized state, returns `[]` | **FAIL** |
| Playwright `RuntimeError` during renewal | Handle gracefully / raise `SessionExpiredException` | Crashes with unhandled `RuntimeError` | **FAIL** |
| Concurrent 401 requests across 4 threads | 1 renewal lock execution | 4 parallel redundant Playwright extractions | **FAIL** |

---

## Unchallenged Areas

- **Telegram API Notifications (`code/notifier.py`)**: Out of scope for Milestone 3 self-healing logic audit (already audited in M2).
- **Playwright DOM selector changes**: Out of scope for scraper HTTP self-healing retry loop (audited in M2).
