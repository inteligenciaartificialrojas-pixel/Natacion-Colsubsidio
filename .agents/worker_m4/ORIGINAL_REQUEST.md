## 2026-08-09T18:50:43Z
You are Worker M4 (teamwork_preview_worker) for Milestone 4 (CI/CD & Local Runner Compatibility).
Working directory: i:\Mi unidad\Natacion Colsubsidio\.agents\worker_m4

Your task:
1. Check code/requirements.txt and ensure playwright>=1.40.0 is present.
2. Check .env.example and ensure COLSUBSIDIO_USER and COLSUBSIDIO_PASS placeholders are present.
3. Check and update .github/workflows/check.yml to:
   - Install system and Playwright Chromium dependencies: `python -m playwright install --with-deps chromium`
   - Cache Playwright browser binaries (`~/.cache/ms-playwright` or platform equivalent) using `actions/cache`
   - Pass `COLSUBSIDIO_USER` and `COLSUBSIDIO_PASS` from repository secrets (`${{ secrets.COLSUBSIDIO_USER }}`, `${{ secrets.COLSUBSIDIO_PASS }}`)
   - Run `python code/main.py --once`
4. Inspect and verify local batch scripts (`actualizar_cookies.bat` and `ejecutar_revisor_local.bat`) to ensure they work smoothly with Python/Playwright setup.
5. Run the unit & integration test suite (`py -m pytest harness/tests` or `pytest harness/tests`) and confirm all tests pass.
6. MANDATORY INTEGRITY WARNING: DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
7. Write your completion report to `i:\Mi unidad\Natacion Colsubsidio\.agents\worker_m4\handoff.md` and notify parent via send_message.
