# Detailed Worker Instructions & Defensive Analysis Report

## 1. Executive Summary & Scope

This document provides exact, step-by-step instructions for the Worker agent to implement defensive JSON parsing, robust exception handling in `code/scraper.py`, and complete the legacy reservation code purge in `harness/tests/`.

### Key Objectives
1. **Harden `code/scraper.py` against malformed or unexpected API responses**:
   - Guard against non-dictionary response bodies (lists, primitives, `None`).
   - Prevent `AttributeError` when accessing dictionary keys with `None` values (e.g. `{"fechas": None}`).
   - Safely iterate and extract nested elements in `horarios` and `zonas`.
   - Expand unauthorized status detection in `_check_unauthorized()` to recognize status codes, error fields, and messages.
   - Wrap non-requests exceptions during session renewal (`_renew_session()`) into `SessionExpiredException`.
   - Catch `AttributeError`, `TypeError`, `KeyError` in public API methods to prevent process crashes.
2. **Purge legacy reservation test cases in `harness/tests/`**:
   - Remove `test_tier4_interactive_telegram_command_handling` from `harness/tests/test_e2e_requirements.py`.
   - Remove `test_tiquetera_id_invalid_string_defaults_to_none` from `harness/tests/test_m2_adversarial.py`.

---

## 2. Defensive Code Analysis of `code/scraper.py`

### 2.1 Unauthorized Response Handling (`_check_unauthorized`)
*Current Vulnerability*:
Lines 96–102 only check `data.get("status") == "Unauthorized"`. If the backend returns `{"status": 401}`, `{"error": "Unauthorized"}`, `{"code": "UNAUTHORIZED"}`, or `{"message": "Session expired"}`, the check fails to trigger session auto-renewal.

*Target Solution*:
Check `data` for dictionary type, then evaluate lower-case string representations of `status`, `code`, `error`, and `message` against unauthorized keywords (`"unauthorized"`, `"401"`, `"session expired"`).

### 2.2 Calendar Availability Endpoint (`fetch_available_dates`)
*Current Vulnerabilities*:
- Line 140: `fechas_dict = data.get("fechas", {})`. If `data` is a list, calling `data.get(...)` raises `AttributeError`. If `data` is `{"fechas": None}`, `fechas_dict` becomes `None`, causing `None.items()` to raise `AttributeError`.
- Line 144: `info.get("disponibilidad")`. If `info` is not a dict, calling `info.get(...)` raises `AttributeError`.
- Lines 149–156: Exception block only catches `SessionExpiredException`, `requests.RequestException`, and `ValueError`. Uncaught `AttributeError`, `TypeError`, or `KeyError` crash the program.

*Target Solution*:
- Ensure `data` is `isinstance(data, dict)`.
- Ensure `fechas_dict` is `isinstance(fechas_dict, dict)`.
- Ensure each `info` item is `isinstance(info, dict)`.
- Broaden exception handling to `(requests.RequestException, ValueError, TypeError, AttributeError, KeyError)`.

### 2.3 Schedule Slots Endpoint (`fetch_slots_for_date`)
*Current Vulnerabilities*:
- Line 208: `horarios = data.get("horarios", [])`. Fails with `AttributeError` if `data` is not a dict. If `data` is `{"horarios": None}`, `horarios` becomes `None`, causing `for h in horarios:` to raise `TypeError`.
- Line 212: `h.get("horario", {}).get("hora_inicio")`. If `"horario": None` in the JSON, `h.get("horario", {})` returns `None`, raising `AttributeError` on `.get("hora_inicio")`.
- Line 217: `hora_inicio.split(":")`. Fails with `AttributeError` if `hora_inicio` is an integer or non-string.
- Lines 221–223: `cupos` handling raises `TypeError` if `cupos` is non-numeric, or if `zonas` is `None` / contains `None` elements.
- Lines 236–243: Uncaught `AttributeError`, `TypeError`, `KeyError` crash the scraper.

*Target Solution*:
- Validate `data` is dict and `horarios` is list.
- Check `h` and `horario_obj` are dicts before accessing properties.
- Ensure `hora_inicio` is `isinstance(hora_inicio, str)` before calling `.split()`.
- Safely parse `cupos` and sum capacity from `zonas` with explicit type casting and type checks.
- Broaden exception handling to `(requests.RequestException, ValueError, TypeError, AttributeError, KeyError)`.

### 2.4 Session Renewal Failure Handling (`_renew_session`)
*Current Vulnerability*:
`extract_colsubsidio_cookies()` can raise unexpected exceptions (e.g. `RuntimeError` if Playwright browser is missing, or `BrowserError`). These leak out uncaught, causing `_execute_with_retry` to fail.

*Target Solution*:
Wrap `extract_colsubsidio_cookies()` in a `try...except Exception as exc:` block and raise `SessionExpiredException(f"Falla al extraer nuevas cookies: {exc}") from exc`.

---

## 3. Worker Implementation Instructions

### Edit 1: `code/scraper.py` — Defensive JSON Parsing & Exception Handling

**File**: `j:\Mi unidad\Natacion Colsubsidio\code\scraper.py`

#### Change 1.1: `_renew_session` Exception Wrapping
Replace lines 61–65 with:
```python
        from get_cookies import extract_colsubsidio_cookies, update_env_file

        try:
            new_cookies = extract_colsubsidio_cookies()
        except Exception as exc:
            logger.error("Error inesperado durante la extracción de cookies: %s", exc)
            raise SessionExpiredException(f"Falla al extraer nuevas cookies: {exc}") from exc

        if not new_cookies or "sistema" not in new_cookies:
            raise SessionExpiredException("No se pudieron obtener nuevas cookies de sesión durante la renovación.")
```

#### Change 1.2: `_check_unauthorized` Enhanced Matching
Replace lines 95–102 with:
```python
        # 2. Verificar si retornó 200 pero es una respuesta JSON con error de no autorizado
        try:
            if "application/json" in response.headers.get("Content-Type", ""):
                data = response.json()
                if isinstance(data, dict):
                    status_val = str(data.get("status", "")).lower()
                    code_val = str(data.get("code", "")).lower()
                    error_val = str(data.get("error", "")).lower()
                    msg_val = str(data.get("message", "")).lower()

                    if (status_val in ["unauthorized", "401"] or
                        code_val in ["unauthorized", "401"] or
                        error_val in ["unauthorized", "401"] or
                        "unauthorized" in msg_val or "session expired" in msg_val):
                        raise SessionExpiredException("Sesión no autorizada en el JSON de respuesta.")
        except (ValueError, TypeError):
            pass
```

#### Change 1.3: `fetch_available_dates` Defensive Parsing
Replace lines 140–156 with:
```python
            data = response.json()
            if not isinstance(data, dict):
                logger.warning("Respuesta inesperada (no es dict) en calendario: %s", type(data))
                return []

            fechas_dict = data.get("fechas")
            if not isinstance(fechas_dict, dict):
                logger.warning("'fechas' no es dict o es None en calendario: %s", type(fechas_dict))
                return []

            available_dates = []
            for fecha_str, info in fechas_dict.items():
                if isinstance(info, dict) and info.get("disponibilidad") is True:
                    available_dates.append(fecha_str)

            logger.info("Fechas disponibles encontradas: %s", available_dates)
            return sorted(available_dates)

        except SessionExpiredException:
            raise
        except (requests.RequestException, ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error al procesar respuesta del calendario: %s", e)
            return []
```

#### Change 1.4: `fetch_slots_for_date` Defensive Parsing
Replace lines 207–244 with:
```python
            data = response.json()
            if not isinstance(data, dict):
                logger.warning("Respuesta inesperada (no es dict) en horarios para %s: %s", date_str, type(data))
                return []

            horarios = data.get("horarios")
            if not isinstance(horarios, list):
                logger.warning("'horarios' no es lista o es None para %s: %s", date_str, type(horarios))
                return []

            slots = []
            for h in horarios:
                if not isinstance(h, dict):
                    continue

                horario_obj = h.get("horario")
                if not isinstance(horario_obj, dict):
                    continue

                hora_inicio = horario_obj.get("hora_inicio")
                if not isinstance(hora_inicio, str) or not hora_inicio:
                    continue

                # Normalizar formato de hora (HH:MM:SS -> HH:MM)
                parts = hora_inicio.split(":")
                hora_formatted = f"{parts[0]}:{parts[1]}" if len(parts) >= 2 else hora_inicio

                # Obtener cupos directamente del objeto padre o calcularlos sumando zonas
                cupos = h.get("cupos")
                if cupos is None:
                    zonas = h.get("zonas")
                    if isinstance(zonas, list):
                        cupos = 0
                        for z in zonas:
                            if isinstance(z, dict):
                                cap = z.get("cupos") if z.get("cupos") is not None else z.get("capacidad_disponible", 0)
                                try:
                                    cupos += int(cap)
                                except (ValueError, TypeError):
                                    pass
                    else:
                        cupos = 0

                try:
                    cupos_int = int(cupos) if cupos is not None else 0
                except (ValueError, TypeError):
                    cupos_int = 0

                if cupos_int > 0:
                    slots.append({
                        "fecha": date_str,
                        "hora": hora_formatted,
                        "cupos": cupos_int,
                        "raw_horario": horario_obj,
                        "zonas": h.get("zonas") if isinstance(h.get("zonas"), list) else []
                    })

            return slots

        except SessionExpiredException:
            raise
        except (requests.RequestException, ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error al procesar respuesta de horarios para %s: %s", date_str, e)
            return []
```

---

### Edit 2: Purge Legacy Reservation Test Code in `harness/tests/`

#### Change 2.1: `harness/tests/test_e2e_requirements.py`
Delete lines 600–638 (`test_tier4_interactive_telegram_command_handling`), which attempts to mock `scraper.book_slot()` and `config.COLSUBSIDIO_TIQUETERA_ID`.

#### Change 2.2: `harness/tests/test_m2_adversarial.py`
Delete lines 56–64 (`test_tiquetera_id_invalid_string_defaults_to_none`), which tests `COLSUBSIDIO_TIQUETERA_ID` environment variable behavior.

---

## 4. Verification Protocol

After implementing the edits above, run pytest to verify that all test suites pass with 0 errors:

```bash
python -m pytest harness/tests/
```

Expected result: 100% test pass rate with no `AttributeError` or `SessionExpiredException` leaks on malformed inputs.
