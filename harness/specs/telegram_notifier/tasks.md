# Tareas de Desarrollo: Notificador de Telegram (`telegram_notifier`)

Lista de tareas para la implementación y verificación del notificador de Telegram.

---

## Checklist de Desarrollo

- [x] **T1 — Configuración del Entorno:**
      Crear/actualizar [config.py](file:///g:/Mi%20unidad/Natacion%20Colsubsidio/code/config.py) para cargar las variables `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID` desde el entorno o archivo `.env`.
      *Cubre: R1.*

- [x] **T2 — Lógica del Notificador:**
      Crear [notifier.py](file:///g:/Mi%20unidad/Natacion%20Colsubsidio/code/notifier.py) con la clase `TelegramNotifier`, métodos de envío de mensajes, construcción de alertas, y lógica de caché para de-duplicación.
      *Cubre: R2, R3, R4, R5.*

- [x] **T3 — Pruebas Unitarias:**
      Escribir `harness/tests/test_notifier.py` para validar el notificador mediante mocks (probando el flujo exitoso, control de excepciones ante errores de red/API y verificación de que se suprimen las alertas repetidas).
      *Cubre: R1, R2, R3, R4, R5.*
