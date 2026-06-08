# Requisitos: Scraper de Colsubsidio (`colsubsidio_scraper`)

Los siguientes requisitos definen el comportamiento esperado del módulo extractor de disponibilidad.

---

## Requisitos Funcionales (EARS)

*   **R1 (Soporte de Sesión Autenticada):**
    El sistema DEBE utilizar la cookie de sesión `sistema` y la cookie `Csrf-Token` cargadas desde la configuración para realizar las consultas de disponibilidad.

*   **R2 (Consulta de Calendario):**
    El sistema DEBE realizar una petición POST a `/v1/centro_entrenamiento/{id}/practicalibre/calendario` para obtener el listado de fechas disponibles.

*   **R3 (Consulta de Horarios y Cupos):**
    CUANDO el calendario retorne fechas con disponibilidad activa (`disponibilidad: True`), el sistema DEBE realizar una petición POST a `/v1/centro_entrenamiento/{id}/practicalibre/disponibilidad?filtrarSinCupo=0` para cada fecha para extraer los horarios específicos y la cantidad de cupos libres.

*   **R4 (Manejo de Expiración de Sesión):**
    SI una petición al API de Colsubsidio retorna un estado HTTP 401 (o redirige a loguearSitio) ENTONCES el sistema DEBE lanzar una excepción de sesión expirada (`SessionExpiredException`) para que el orquestador notifique al usuario la necesidad de renovar la cookie.

*   **R5 (Manejo de Caídas del Servicio):**
    SI la API de Colsubsidio no responde (timeout) o retorna códigos HTTP 5xx ENTONCES el sistema DEBE registrar la advertencia en el log, esperar al siguiente ciclo y continuar sin interrumpir el loop principal.
