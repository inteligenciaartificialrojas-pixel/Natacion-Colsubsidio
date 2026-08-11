# Challenge Report — Milestone 2 (Challenger 2)

## Challenge Summary

**Overall risk assessment**: **HIGH**

This adversarial evaluation stress-tested `login_and_get_cookies()`, custom parameter handling (`user`, `password`, `headless`), and `.env` file updating logic (`update_env_file()`) in `code/get_cookies.py`. A new test suite (`harness/tests/test_get_cookies_adversarial.py`) was constructed to empirically reproduce failure modes and vulnerabilities.

---

## Challenges

### 1. [Critical] Destructive Overwrite on Partial Cookie Dictionaries & Non-Atomic `.env` Writes
- **Assumption challenged**: `update_env_file()` safely updates specified cookies while preserving existing `.env` variables and token states.
- **Attack scenario**: When `update_env_file({"sistema": "new_val"})` is called without `"Csrf-Token"` in the dictionary, line 309 evaluates `cookies.get('Csrf-Token', '')` to `""`. This rewrites `COLSUBSIDIO_CSRF_TOKEN=` in `.env` with an empty string, wiping out pre-existing valid CSRF tokens. Furthermore, direct use of `open(env_path, "w")` truncates `.env` before writing; any interruption (power loss, process termination, disk full) results in 0-byte file loss.
- **Blast radius**: Permanent deletion of active credentials and configuration variables in `.env`.
- **Mitigation**: 
  1. Check explicit key presence (`if 'Csrf-Token' in cookies:`) before updating existing lines.
  2. Implement atomic file writes using a temporary file in the same directory and `os.replace()`.

### 2. [High] Process-Global Environment Pollution & Playwright Thread-Safety in Concurrent Executions
- **Assumption challenged**: `login_and_get_cookies()` can be safely invoked concurrently across multiple threads.
- **Attack scenario**: 
  1. `login_and_get_cookies()` mutates process-global state (`os.environ["COLSUBSIDIO_SISTEMA_COOKIE"]` and `config.COLSUBSIDIO_SISTEMA_COOKIE`). Concurrent execution across threads leads to cross-thread data races and cookie leakage.
  2. Playwright's `sync_playwright()` is bound to a single thread's event loop. Invoking `login_and_get_cookies()` simultaneously in multi-threaded contexts triggers uncaught `RuntimeError` / Playwright event loop crashes.
- **Blast radius**: Cross-session data leakage in multi-user/multi-threaded runners and unhandled process crashes.
- **Mitigation**: Introduce thread locking (`threading.Lock()`), isolate environment variable mutations, or require process-level isolation for parallel browser invocations.

### 3. [Medium] Falsy Parameter Fallback (`user=""`, `password=""`)
- **Assumption challenged**: Explicit arguments supplied to `login_and_get_cookies(user, password)` override default environment/config fallbacks.
- **Attack scenario**: Using `user_val = user or os.environ.get("COLSUBSIDIO_USER")` causes Python to treat `""` (empty string) as falsy. Passing `user=""` or `password=""` (e.g., during tests or intentional credential reset) silently falls back to reading `COLSUBSIDIO_USER` from `.env`.
- **Blast radius**: Inability to supply empty parameters programmatically; silent fallback to default credentials.
- **Mitigation**: Use `user_val = user if user is not None else os.environ.get("COLSUBSIDIO_USER")`.

### 4. [Medium] Missing Type Coercion for Numeric Credential Inputs
- **Assumption challenged**: Callers will always pass `str` instances for `user` and `password`.
- **Attack scenario**: Passing document numbers as integers (e.g. `user=1002559691` or `password=123456`) causes Playwright's `page.fill(user_sel, user_val)` to crash with `TypeError: expected string, got int`.
- **Blast radius**: Unexpected crashes when calling authentication functions with uncasted numeric types.
- **Mitigation**: Add explicit string coercion: `user_val = str(user_val) if user_val is not None else None`.

### 5. [Medium] Duplicate Key Creation on Spaced `.env` Lines & Newline Injection
- **Assumption challenged**: `.env` parser correctly identifies existing keys regardless of formatting and sanitizes values.
- **Attack scenario**:
  1. If `.env` contains spaces around equals (e.g. `COLSUBSIDIO_SISTEMA_COOKIE = old_val`), `stripped.startswith("COLSUBSIDIO_SISTEMA_COOKIE=")` fails to match, leaving the old line intact and appending a duplicate key.
  2. If cookie values contain newlines (`val\nEVIL_VAR=hacked`), raw line formatting appends multiple lines, injecting arbitrary environment variables into `.env`.
- **Blast radius**: `.env` corruption and arbitrary environment variable injection.
- **Mitigation**: Normalize key matching (e.g., split on `=`) and strip/sanitize newlines from cookie values before writing.

### 6. [Low] Deprecated `tempfile.mktemp` in Local Browser Cookie Extraction
- **Assumption challenged**: Temporary file creation in `extract_local_browser_cookies()` is thread-safe.
- **Attack scenario**: Line 235 uses `tempfile.mktemp(suffix=".sqlite")`, which is vulnerable to TOCTOU race conditions and filename collisions during concurrent calls.
- **Blast radius**: Temporary file collision or `sqlite3.OperationalError: database is locked`.
- **Mitigation**: Replace `tempfile.mktemp()` with `tempfile.NamedTemporaryFile()`.

---

## Stress Test Results

| Scenario | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|
| Concurrent `.env` updates across 10 threads | File remains intact with valid keys | Race condition during non-atomic write | **FAIL** |
| Partial cookie dict `{"sistema": "new"}` update | Preserve existing `COLSUBSIDIO_CSRF_TOKEN` | Sets `COLSUBSIDIO_CSRF_TOKEN=` (empty) | **FAIL** |
| Explicit `user=""` parameter input | Use `""` as user value | Falls back to `COLSUBSIDIO_USER` from `.env` | **FAIL** |
| Numeric user input (`user=1002559691`) | String filled into DOM | Playwright throws `TypeError` | **FAIL** |
| `.env` with spaces (`KEY = val`) | Replace existing key | Appends duplicate line at end of file | **FAIL** |
| Cookie with newline (`val\nINJECT=1`) | Sanitize value or throw error | Injects `INJECT=1` variable into `.env` | **FAIL** |

---

## Unchallenged Areas

- **Windows DPAPI Native C-Types Invocation**: `decrypt_key_with_dpapi()` depends on Windows `crypt32.dll`. Verification was conducted in Windows environment context; non-Windows fallback (`extract_local_browser_cookies` returns empty) was confirmed logically.
