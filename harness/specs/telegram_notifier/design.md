# Diseño Técnico: Notificador de Telegram (`telegram_notifier`)

Este documento detalla las especificaciones de diseño técnico para la implementación del módulo de notificaciones.

---

## 1. Módulos y Clases

El código se implementará en [notifier.py](file:///g:/Mi%20unidad/Natacion%20Colsubsidio/code/notifier.py).

### Clase `TelegramNotifier`

```python
class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: str | None = None, cache_duration_seconds: int = 3600):
        """
        Inicializa el notificador. Si token o chat_id no son suministrados,
        se leen de las variables de entorno a través de config.py.
        """
        self.token = token
        self.chat_id = chat_id
        self.cache_duration_seconds = cache_duration_seconds
        # Estructura de caché: { "key": epoch_timestamp }
        self._sent_alerts: dict[str, float] = {}

    def _generate_key(self, venue: str, date_str: str, time_str: str, slots: int) -> str:
        """Genera una llave única para identificar el cupo."""
        return f"{venue}:{date_str}:{time_str}:{slots}"

    def prune_cache(self) -> None:
        """Elimina elementos de la caché que hayan superado la duración de vida útil."""
        # ...

    def send_message(self, text: str) -> bool:
        """
        Envía un mensaje de texto simple en formato Markdown.
        Retorna True si fue exitoso, False de lo contrario.
        """
        # ...

    def notify_slot(self, venue: str, date_str: str, time_str: str, slots: int) -> bool:
        """
        Genera un mensaje formateado y lo envía si no ha sido notificado previamente
        dentro de la ventana de supresión de spam.
        """
        # ...
```

---

## 2. Control de Duplicados (Caché en Memoria)

*   Para evitar el spam, antes de enviar un mensaje se calcula una clave:
    `key = f"{venue}:{date_str}:{time_str}:{slots}"`
*   Si la clave existe en `_sent_alerts` y el tiempo transcurrido es menor a `cache_duration_seconds` (3600 segundos por defecto), la alerta se omite.
*   Periódicamente (durante cada llamada a `notify_slot`), se llamará a `prune_cache` para evitar crecimiento de memoria innecesario.

---

## 3. Manejo de Errores e Integración HTTP

*   Se utilizará la biblioteca `requests` para realizar peticiones HTTP síncronas.
*   URL del Endpoint: `https://api.telegram.org/bot<token>/sendMessage`
*   Payload:
    ```json
    {
      "chat_id": "<chat_id>",
      "text": "<mensaje>",
      "parse_mode": "Markdown"
    }
    ```
*   Timeout: Se definirá un timeout estricto de 10 segundos en las peticiones para evitar hilos suspendidos.
*   Manejo de excepciones: Se envolverán las llamadas en bloques `try/except requests.RequestException`.

---

## 4. Alternativas Descartadas

*   **Alternativa Descartada:** Usar bases de datos persistentes (SQLite, JSON local) para la caché de duplicados.
    *   *Razón:* Al tratarse de un Nivel 1 en bucle continuo de memoria, una caché en memoria basada en diccionarios es más rápida, simple de probar con mocks y no introduce archivos residuales en disco (C5 de Checkpoints).
