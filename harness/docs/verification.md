# Verificación del Revisor de Natación

Toda característica añadida debe ser verificada antes de declararse como finalizada (`done`).

## Pruebas Automáticas (Pytest)

Las pruebas deben residir en `harness/tests/` y tener nombres en la forma `test_<modulo>.py`.

### 1. Mocks de Red
Debido a que el scraper y el notificador hacen llamadas HTTP a servicios externos (Colsubsidio y Telegram), los tests unitarios **no deben realizar peticiones reales a Internet**.
*   Utilizar `unittest.mock` (o plugins de pytest como `pytest-mock` / `respx`) para interceptar peticiones de `httpx` o `requests`.
*   Simular respuestas de éxito (ej. JSON con cupos) y respuestas de error (ej. Timeout, HTTP 500, Token no válido).

### 2. Trazabilidad
En la bitácora de la feature (`progress/impl_<name>.md` o en las tareas del spec), se debe dejar constancia de qué test cubre qué requisito:
*   `R1 (Envío de alerta)` ➔ Cubierto por `test_send_notification_success`
*   `R2 (De-duplicación)` ➔ Cubierto por `test_no_duplicate_notifications`

## Verificación de Cierre de Sesión

Antes de terminar la sesión, corre:
```bash
python3 -m pytest tests/ -v
```
Todos los tests deben estar en verde.
