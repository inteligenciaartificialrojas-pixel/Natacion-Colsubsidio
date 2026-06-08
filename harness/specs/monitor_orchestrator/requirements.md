# Requisitos: Orquestador y Filtros de Monitoreo (`monitor_orchestrator`)

Los siguientes requisitos definen el comportamiento esperado del bucle principal de control y los filtros de negocio.

---

## Requisitos Funcionales (EARS)

*   **R1 (Inicialización):**
    El sistema DEBE inicializar los módulos `ColsubsidioScraper` y `TelegramNotifier` al arrancar.

*   **R2 (Ejecución Periódica):**
    El sistema DEBE ejecutar un ciclo de consulta de disponibilidad de forma periódica en base al intervalo configurado (`DEFAULT_CHECK_INTERVAL_SECONDS`).

*   **R3 (Filtro de Sedes de Interés):**
    El sistema DEBE consultar únicamente las sedes definidas en `VENUE_SERVICE_IDS` (El Cubo y Plaza de las Américas).

*   **R4 (Filtro de Horario - Entre Semana):**
    MIENTRAS la fecha analizada sea un día entre semana (lunes a viernes), el sistema DEBE omitir cualquier cupo cuya hora de inicio no esté dentro del rango de interés (entre las 6:00 PM / 18:00 y las 8:00 PM / 20:00, inclusive).

*   **R5 (Filtro de Horario - Fin de Semana):**
    MIENTRAS la fecha analizada sea un fin de semana (sábado o domingo), el sistema DEBE aceptar y alertar para cualquier horario disponible sin restricciones.

*   **R6 (Gestión de Expiración de Sesión):**
    CUANDO se reciba una excepción `SessionExpiredException` durante el escaneo, el sistema DEBE enviar un mensaje de alerta a Telegram informando al usuario sobre la expiración de su sesión, limitando este mensaje a un máximo de una vez cada 24 horas.
