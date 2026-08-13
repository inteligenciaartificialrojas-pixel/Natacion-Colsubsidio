# TEST READY — Colsubsidio Swimming Availability Monitor E2E Suite

- **Status**: COMPLETE
- **Suite Location**: `harness/tests/test_e2e_requirements.py`
- **Total Test Cases**: 27
- **Test Framework**: `pytest`
- **Target Execution Command**: `pytest harness/tests/test_e2e_requirements.py`

## Suite Coverage Breakdown

| Tier | Category / Feature Area | Test Cases | Description & Coverage |
|------|-------------------------|------------|------------------------|
| Tier 1 | Availability Scraper & Cookie Session Handling | 10 | Endpoint querying (`calendario`, `disponibilidad`), session cookies (`sistema`, `sitio`, `Csrf-Token`), HTTP 401 / JSON / HTML expiration handling, auto-retry renewal, network resilience, slot time & capacity normalization |
| Tier 2 | Strict Schedule Filter Engine & Edge Cases | 7 | Weekday evening schedule (Mon-Fri 18:00-20:00), weekday mid-day rejection, weekend 24h coverage, Colombian fixed holidays 24h, Ley Emiliani & Easter mobile holidays, boundary parsing, R2 requirements audit |
| Tier 3 | Clean Telegram Notifications & Deduplication | 7 | Notifier initialization, clean Markdown message formatting, slot state deduplication, slot delta detection, `force=True` override, cache pruning expiration, `.cooldown_state` and `.last_slots.json` disk state persistence |
| Tier 4 | End-to-End Execution Workflow | 5 | `check_venues` multi-venue orchestration, `find_new_slots` delta calculation, `main()` `--once` mode execution, `SessionExpiredException` handling with alert escalation, interactive `/agendar` Telegram command processing |

## Test Inventory Table

| Test Function Name | Tier | Scope |
|-------------------|------|-------|
| `test_tier1_scraper_init_and_headers` | Tier 1 | Header and initial cookie configuration |
| `test_tier1_update_session_credentials` | Tier 1 | In-memory session cookie and header updates |
| `test_tier1_fetch_available_dates_endpoint_payload` | Tier 1 | POST payload format for `/calendario` |
| `test_tier1_fetch_slots_for_date_endpoint_payload` | Tier 1 | POST payload format for `/disponibilidad` |
| `test_tier1_slot_normalization_time_and_capacity` | Tier 1 | Time string normalization & zone capacity summation |
| `test_tier1_session_expired_http_401` | Tier 1 | HTTP 401 status code exception handling |
| `test_tier1_session_expired_json_unauthorized` | Tier 1 | Status "Unauthorized" JSON response handling |
| `test_tier1_session_expired_html_redirect` | Tier 1 | HTML redirect to loguearSitio exception handling |
| `test_tier1_auto_retry_on_401_success` | Tier 1 | Session renewal and automatic retry flow |
| `test_tier1_network_and_json_error_resilience` | Tier 1 | HTTP 500, network timeouts, bad JSON resilience |
| `test_tier2_weekday_evening_schedule` | Tier 2 | Mon-Fri preferred schedule window validation |
| `test_tier2_weekday_outside_hours` | Tier 2 | Mon-Fri non-preferred schedule rejection |
| `test_tier2_weekend_24h_coverage` | Tier 2 | Saturday & Sunday 24h coverage |
| `test_tier2_colombian_fixed_holidays_24h_coverage` | Tier 2 | Fixed Colombian national holidays 24h coverage |
| `test_tier2_colombian_emiliani_and_easter_holidays` | Tier 2 | Ley Emiliani & Easter mobile holidays calculation |
| `test_tier2_boundary_time_string_parsing` | Tier 2 | Malformed time/date string safety |
| `test_tier2_spec_schedule_rules_audit` | Tier 2 | R2 schedule window requirements audit |
| `test_tier3_notifier_init_and_credentials` | Tier 3 | Notifier init & fallback without credentials |
| `test_tier3_clean_message_formatting` | Tier 3 | Structured Markdown Telegram notification format |
| `test_tier3_slot_state_deduplication` | Tier 3 | Slot deduplication across identical scans |
| `test_tier3_slot_state_delta_detection` | Tier 3 | New slot and cupo count increase detection |
| `test_tier3_force_send_override` | Tier 3 | `force=True` bypass of deduplication cache |
| `test_tier3_cache_pruning_expiration` | Tier 3 | Cache TTL expiration and entry pruning |
| `test_tier3_cooldown_state_and_last_slots_persistence` | Tier 3 | `.cooldown_state` and `.last_slots.json` file IO |
| `test_tier4_full_check_venues_workflow` | Tier 4 | Multi-venue scanning, filtering, and saving workflow |
| `test_tier4_find_new_slots_orchestration` | Tier 4 | Slot comparison & delta calculation logic |
| `test_tier4_main_once_mode_execution` | Tier 4 | `main()` `--once` CLI argument execution |
| `test_tier4_session_expiration_workflow_in_main` | Tier 4 | Unrecovered 401 escalation to Telegram alert in `main()` |
| `test_tier4_interactive_telegram_command_handling` | Tier 4 | Interactive `/agendar` command parser & reservation |

## Verification Command
```bash
pytest harness/tests/test_e2e_requirements.py
```
