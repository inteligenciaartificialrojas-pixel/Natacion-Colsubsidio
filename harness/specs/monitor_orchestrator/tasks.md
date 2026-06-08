# Tareas de Desarrollo: Orquestador y Filtros (`monitor_orchestrator`)

Lista de tareas para la implementación y verificación del bucle de control.

---

## Checklist de Desarrollo

- [x] **T1 — Lógica de Filtros y Orquestación:**
      Implementar en [main.py](file:///g:/Mi%20unidad/Natacion%20Colsubsidio/code/main.py) las funciones `is_within_preferred_schedule` y `check_venues` que ejecutan la consulta secuencial de sedes y descartan cupos fuera de los horarios de preferencia del usuario.
      *Cubre: R1, R2, R3, R4, R5.*

- [x] **T2 — Control de Expiración del Bucle:**
      Implementar en [main.py](file:///g:/Mi%20unidad/Natacion%20Colsubsidio/code/main.py) el bucle principal (`while True`) con captura de la excepción `SessionExpiredException` y envío controlado de la alerta de expiración en Telegram con un cool-down de 24 horas.
      *Cubre: R6.*

- [x] **T3 — Pruebas Unitarias:**
      Escribir `harness/tests/test_orchestrator.py` para validar la lógica de filtrado de horarios (días de semana y fines de semana), el flujo del loop principal de chequeo de sedes, y el control de alertas únicas de sesión expirada.
      *Cubre: R4, R5, R6.*
