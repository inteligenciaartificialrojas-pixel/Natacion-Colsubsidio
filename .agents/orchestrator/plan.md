# Project Plan — Colsubsidio Swimming Availability Self-Healing Workflow

## Overview
Automate session login using Playwright and make the Colsubsidio Swimming availability checking workflow fully self-healing and resilient against session expiration.

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Exploration & Architecture Analysis | Investigate existing codebase (`code/get_cookies.py`, `code/scraper.py`, `code/config.py`, `code/main.py`, `.env.example`, workflows), Playwright environment, login flow, cookie mechanisms, and state caching. | None | IN_PROGRESS |
| M2 | Playwright Automated Login & Session Renewal Module | Create automated Playwright login helper in Python, support headless authentication with `COLSUBSIDIO_USER` and `COLSUBSIDIO_PASS`, extract `sistema` & `Csrf-Token` cookies, update `.env` and in-memory structures. | M1 | PLANNED |
| M3 | Scraper Self-Healing & Session Retry Integration | Integrate session renewal into `scraper.py`, handle HTTP 401 / `SessionExpiredException`, trigger Playwright renewal, refresh headers/cookies, seamlessly retry requests without crashing. | M2 | PLANNED |
| M4 | CI/CD & Local Runner Compatibility | Update `code/requirements.txt`, `.env.example`, `.github/workflows/check.yml`, helper scripts (`actualizar_cookies.bat`, `ejecutar_revisor_local.bat`) to install Playwright and Chromium dependencies and ensure exit code 0 on session renewal. | M3 | PLANNED |
| M5 | E2E Testing, Adversarial Hardening & Final Audit | Run unit/E2E test suite, test expired cookie recovery, verify Telegram notifications and slot filtering logic preservation, perform forensic integrity audit. | M4 | PLANNED |

## Detailed Plan Execution Strategy
For each milestone:
1. Dispatch 3 Explorer agents for technical investigation & solution strategy design.
2. Dispatch 1 Worker agent to implement solution and run verification builds/tests.
3. Dispatch 2 Reviewer agents for code quality, specification compliance, and security verification.
4. Dispatch 2 Challenger agents for adversarial testing & edge case verification.
5. Dispatch 1 Forensic Auditor (`teamwork_preview_auditor`) for integrity verification (BINARY VETO).
6. Evaluate gate criteria and proceed or iterate.
