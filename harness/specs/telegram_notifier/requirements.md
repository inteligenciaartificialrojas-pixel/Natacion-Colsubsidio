# Requisitos: Notificador de Telegram (`telegram_notifier`)

Los siguientes requisitos definen el comportamiento esperado del módulo notificador.

---

## Requisitos Funcionales (EARS)

*   **R1 (Configuración de Credenciales):**
    El sistema DEBE obtener el `TELEGRAM_TOKEN` y el `TELEGRAM_CHAT_ID` desde la configuración del entorno (`code/config.py`).

*   **R2 (Envío de Mensajes):**
    El sistema DEBE enviar mensajes utilizando la API oficial de bots de Telegram (`https://api.telegram.org/bot<token>/sendMessage`) con parseo en formato Markdown.

*   **R3 (Control de Errores):**
    SI ocurre un error de conexión (timeout, DNS) o un error de API HTTP (ej. HTTP 400, 401, 403) ENTONCES el sistema DEBE registrar la advertencia en el log de auditoría y retornar `False` (o lanzar una excepción controlada) sin detener la ejecución de la aplicación.

*   **R4 (Control de Duplicados - Cache):**
    El sistema DEBE almacenar en memoria el identificador del cupo notificado (combinación de `sede`, `fecha`, `hora` y `cupos`) junto con la marca de tiempo de envío.

*   **R5 (Supresión de Alertas Repetidas):**
    MIENTRAS un cupo disponible ya haya sido notificado con éxito en los últimos 60 minutos, el sistema DEBE omitir el envío de una nueva alerta para evitar el spam.
