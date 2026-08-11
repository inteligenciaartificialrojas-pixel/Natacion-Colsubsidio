# Project: Colsubsidio Swimming Availability Self-Healing Workflow

## Architecture
Automated session login using Playwright integrated into Python web scraping workflow for Colsubsidio swimming venue availability.
Components:
- `code/get_cookies.py`: Login automation & cookie extraction (Playwright headless Chromium).
- `code/scraper.py`: Availability scraping, HTTP request execution, HTTP 401 / session expiration detection & automatic re-login retry trigger.
- `code/config.py`: Environment configuration loading (`COLSUBSIDIO_USER`, `COLSUBSIDIO_PASS`, headers, cookie state).
- `code/notifier.py`: Telegram notifications & interactive command handling.
- `code/main.py`: CLI entry point (`--once`, scheduled loop).
- `.github/workflows/check.yml`: GitHub Actions workflow setup & runner execution.

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Exploration & Architecture Analysis | Codebase investigation, Playwright environment check, login flow analysis | None | DONE |
| 2 | Playwright Automated Login & Session Renewal Module | Implement `get_cookies.py` using Playwright to handle login, cookie extraction (`sistema`, `Csrf-Token`), `.env` sync | M1 | DONE |
| 3 | Scraper Self-Healing Integration | Integrate automatic session recovery into `scraper.py` on 401 / expired session | M2 | DONE |
| 4 | CI/CD & Local Runner Compatibility | Update `requirements.txt`, `.env.example`, `.github/workflows/check.yml`, helper scripts | M3 | DONE |
| M5 | E2E Verification & Adversarial Hardening | Full test suite execution, expired session recovery simulation, final audit | M4 | DONE |

## Interface Contracts
- **`get_cookies.login_and_get_cookies(user, password) -> dict`**: Returns fresh cookie dictionary containing `sistema` and `Csrf-Token` (or updates `.env` and headers dict).
- **`scraper.Scraper.fetch_availability()`**: Catches 401 / `SessionExpiredException`, calls login helper, updates headers/cookies, and retries request seamlessly up to retry limit.

## Code Layout
- `code/get_cookies.py`: Playwright browser automation & session helper.
- `code/scraper.py`: Core scraping & self-healing retry logic.
- `code/config.py`: Configuration & environment loading.
- `code/notifier.py`: Telegram notifications & commands.
- `code/main.py`: CLI execution script.
- `code/requirements.txt`: Dependencies including `playwright`.
- `.github/workflows/check.yml`: Workflow file for CI/CD scheduled execution.
