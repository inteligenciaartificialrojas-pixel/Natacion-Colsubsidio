# Original User Request

## 2026-08-09T18:17:56Z

Automate session login using Playwright and make the Colsubsidio Swimming availability checking workflow fully self-healing and resilient against session expiration.

Working directory: `i:/Mi unidad/Natacion Colsubsidio`
Integrity mode: development

## Requirements

### R1. Automated Playwright Login & Session Renewal
Implement a Playwright-based headless browser login module in Python that automates the login flow on Colsubsidio (`https://www.diversioncolsubsidio.com/sistema.php/default/loguearSitio`) using credentials `COLSUBSIDIO_USER` and `COLSUBSIDIO_PASS` from environment variables.
When `scraper.py` detects an HTTP 401 Unauthorized or expired session, automatically invoke Playwright to perform login, capture fresh `sistema` and `Csrf-Token` cookies, update `.env` (and session headers in memory), and retry the failed API request seamlessly.

### R2. CI/CD & Local Runner Compatibility
Update `code/requirements.txt`, `.env.example`, and `.github/workflows/check.yml` to install Playwright dependencies (`playwright` and `playwright install chromium`), ensuring that both local execution and scheduled GitHub Actions runs automatically renew sessions without crashing with exit code 1.

### R3. Preserved Business Logic & Notifications
Preserve all existing scraper features: filtering preferred venue schedules (El Cubo, Plaza de las Américas, Club La Colina), checking weekday/weekend rules, sending Telegram notifications, handling state caching (`.cooldown_state`, `.last_slots.json`), and interactive Telegram reservation commands.

## Acceptance Criteria

### Automated Login & Recovery
- [ ] An automated login helper using Playwright launches headless Chromium, authenticates using `COLSUBSIDIO_USER` and `COLSUBSIDIO_PASS`, and extracts valid `sistema` & `Csrf-Token` cookies.
- [ ] `scraper.py` catches `SessionExpiredException` / HTTP 401, triggers Playwright session renewal, updates session cookies in memory and in `.env`, and successfully retries the request without failing the process.

### GitHub Actions & Execution
- [ ] Running `python code/main.py --once` in an environment with expired or missing cookies successfully logs in via Playwright, fetches availability, and completes with exit code 0.
- [ ] GitHub Actions workflow `.github/workflows/check.yml` installs Playwright and Chromium dependencies and runs `main.py` without exit code 1 errors.

### Integrity & Quality
- [ ] Automated tests or verification scripts confirm that expired cookie scenarios automatically recover and fetch availability.
- [ ] No regression in Telegram notifications or slot filtering logic.
