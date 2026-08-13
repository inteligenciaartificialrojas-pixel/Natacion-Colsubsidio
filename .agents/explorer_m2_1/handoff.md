# Handoff Report - Feature F3 (Strict Schedule Filter Engine & Holidays)

## 1. Observation
- **Requirement Source**: `ORIGINAL_REQUEST.md` (§ R2, lines 55-58):
  > "Lunes a Viernes: turnos antes de las 7:00 AM o después de las 5:00 PM (17:00).
  > Sábados y Domingos: cualquier hora del día."
  > Acceptance Criteria (line 71): "Filtro estricto de horarios aplicado correctamente (L-V < 7am ó > 5pm; S-D 24h)."
  > (Rule details: 07:00 is NOT allowed; 17:00 IS allowed).

- **Architecture Contract**: `PROJECT.md` (lines 19, 42):
  > Line 19 (F3): "Filter free slots: Mon-Fri < 07:00 or >= 17:00 (17:00-23:59), Sat-Sun & Colombian Holidays 24h"
  > Line 42: `is_within_preferred_schedule(dt: datetime) -> bool`

- **Current Implementation in `code/main.py` (lines 156-176)**:
  ```python
  def is_within_preferred_schedule(date_str: str, time_str: str) -> bool:
      """
      Evalúa si la fecha y hora corresponden a las preferencias del usuario:
      - Sábados, Domingos y Festivos colombianos: Cualquier horario.
      - Lunes a Viernes no festivos: Hora de inicio entre las 18:00 y las 20:00.
      """
      try:
          dt = datetime.strptime(date_str, "%Y-%m-%d")
          day_of_week = dt.weekday()  # 0 es Lunes, 6 es Domingo
          
          # Si es fin de semana (sábado/domingo) o es día festivo
          if day_of_week >= 5 or is_colombian_holiday(dt.date()):
              return True
          else:
              # Lunes a Viernes normal
              hour = int(time_str.split(":")[0])
              return 18 <= hour <= 20
      except Exception as e:
          logger.error("Error al evaluar horario preferido (%s, %s): %s", date_str, time_str, e)
          return False
  ```

- **Current Implementation in `code/config.py` (lines 46-48)**:
  ```python
  # Reglas de horario para días entre semana (L-V)
  WEEKDAY_START_HOUR: int = 18  # 6:00 PM
  WEEKDAY_END_HOUR: int = 20    # 8:00 PM
  ```

- **Colombian Holiday Check in `code/main.py` (lines 91-154)**:
  `is_colombian_holiday(target_date: date) -> bool` is implemented dynamically using the Meeus/Jones/Butcher Easter algorithm and Ley 51 de 1983 (Ley Emiliani). Results are cached in `_holidays_cache: dict[int, set[date]]`. It covers all 18 Colombian holidays (6 fixed non-Emiliani, 7 fixed Emiliani-transferable, 2 Easter non-Emiliani, and 3 Easter Emiliani-transferable) with zero external dependencies (no third-party `holidays` package required).

## 2. Logic Chain
1. **Schedule Window Discrepancy**:
   - `ORIGINAL_REQUEST.md` (§ R2) and `PROJECT.md` (F3) specify that weekday slots must be accepted if `< 07:00` OR `>= 17:00`.
   - `code/main.py` (lines 171-172) currently checks `18 <= hour <= 20`.
   - **Effect**:
     - Morning slots before 07:00 (e.g. 06:00, 06:30) are incorrectly rejected (`False`).
     - 17:00 (5:00 PM) slot is incorrectly rejected (`False`).
     - Evening slots after 20:00 (e.g. 21:00, 22:00) are incorrectly rejected (`False`).
     - 07:00 slot is correctly rejected (`False`) because `hour = 7` is neither `< 7` nor `>= 17`.

2. **Function Signature Polymorphism**:
   - `PROJECT.md` (line 42) defines the interface contract as `is_within_preferred_schedule(dt: datetime) -> bool`.
   - `code/main.py` (line 156) defines `is_within_preferred_schedule(date_str: str, time_str: str) -> bool`.
   - **Effect**: Callers attempting to pass a single `datetime` instance trigger a `TypeError`. Supporting both `datetime`/`date` objects and `(date_str, time_str)` string pairs ensures adherence to `PROJECT.md` contract while maintaining backward compatibility.

3. **Config Constant Alignment**:
   - `code/config.py` hardcodes `WEEKDAY_START_HOUR = 18` and `WEEKDAY_END_HOUR = 20`.
   - Updating `code/config.py` to define `WEEKDAY_MORNING_END_HOUR = 7` and `WEEKDAY_EVENING_START_HOUR = 17` aligns global configuration with business requirements.

4. **Holiday Determination**:
   - `is_colombian_holiday` in `code/main.py` correctly calculates Easter (Jueves/Viernes Santo, Ascensión, Corpus Christi, Sagrado Corazón) and Ley Emiliani transfers for fixed holidays.
   - Uses zero external dependencies (std lib only), cached in memory per year.

## 3. Caveats
No caveats.

## 4. Conclusion
The schedule filter engine and config constants require refactoring to implement the R2 rule (< 07:00 or >= 17:00 for weekdays; 24h for weekends and holidays) and support datetime object inputs.

### Recommended Modifications:

#### A. Modifications in `code/config.py`:
Replace lines 46-48 with:
```python
# Reglas de horario para días entre semana (L-V)
# Turnos antes de las 07:00 AM (< 07:00) o después/igual a las 05:00 PM (>= 17:00)
WEEKDAY_MORNING_END_HOUR: int = 7     # Turnos < 07:00 (07:00 no permitido)
WEEKDAY_EVENING_START_HOUR: int = 17  # Turnos >= 17:00 (17:00 permitido)
```

#### B. Modifications in `code/main.py`:
1. Update imports from `config.py`:
```python
from config import (
    VENUE_SERVICE_IDS,
    DEFAULT_CHECK_INTERVAL_SECONDS,
    WEEKDAY_MORNING_END_HOUR,
    WEEKDAY_EVENING_START_HOUR,
)
```
2. Refactor `is_within_preferred_schedule`:
```python
def is_within_preferred_schedule(date_or_dt: datetime | date | str, time_str: str | None = None) -> bool:
    """
    Evalúa si la fecha y hora corresponden a las preferencias del usuario:
    - Sábados, Domingos y Festivos colombianos: Cualquier horario (24 horas).
    - Lunes a Viernes no festivos: Turnos antes de las 07:00 AM (< 07:00) o después/igual a las 05:00 PM (>= 17:00).
      (07:00 NO está permitido; 17:00 SÍ está permitido).
    Soporta argumentos polimórficos: instancia de datetime/date o cadenas (date_str, time_str).
    """
    try:
        if isinstance(date_or_dt, (datetime, date)):
            if isinstance(date_or_dt, datetime):
                dt_obj = date_or_dt
                target_date = dt_obj.date()
                hour = dt_obj.hour
            else:
                target_date = date_or_dt
                if time_str is None:
                    return False
                hour = int(time_str.split(":")[0])
        else:
            dt_obj = datetime.strptime(str(date_or_dt), "%Y-%m-%d")
            target_date = dt_obj.date()
            if time_str is None:
                return False
            hour = int(time_str.split(":")[0])

        # Sábados, domingos o festivos en Colombia -> 24h disponible
        if target_date.weekday() >= 5 or is_colombian_holiday(target_date):
            return True
        else:
            # Lunes a Viernes normal: < 07:00 ó >= 17:00
            return hour < WEEKDAY_MORNING_END_HOUR or hour >= WEEKDAY_EVENING_START_HOUR
    except Exception as e:
        logger.error("Error al evaluar horario preferido (%s, %s): %s", date_or_dt, time_str, e)
        return False
```

## 5. Verification Method
- Execute pytest tests:
  `pytest harness/tests/test_e2e_requirements.py`
  `pytest harness/tests/test_orchestrator.py`
- Verify that weekday slots at 06:00, 06:30, 17:00, 18:00, 21:00 evaluate to `True`, slot 07:00 evaluates to `False`, mid-day weekday slots (e.g. 12:00) evaluate to `False`, and weekend/holiday slots evaluate to `True`.
