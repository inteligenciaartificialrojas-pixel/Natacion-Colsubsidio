# Proceso Spec Driven Development (SDD) en Revisor de Natación

Este proyecto utiliza SDD para gobernar la evolución del código de forma segura y estructurada.

## Estructura de Specs

Cada característica (`telegram_notifier`, `colsubsidio_scraper`, `monitor_orchestrator`) tiene su carpeta dedicada en `harness/specs/`:

```
harness/specs/<feature-name>/
├── requirements.md   # Requisitos funcionales en notación EARS
├── design.md         # Diseño de clases, funciones y dependencias
└── tasks.md          # Lista de tareas específicas de desarrollo
```

## Notación EARS para Requisitos

Los requisitos en `requirements.md` se escriben con la sintaxis **EARS** (Easy Approach to Requirements Syntax). Cada requerimiento tiene un ID estable (`R1`, `R2`, ...) y sigue una plantilla fija:

| Patrón | Plantilla | Ejemplo en Revisor de Natación |
| :--- | :--- | :--- |
| **Ubicuo** | `El sistema DEBE <acción>.` | `El sistema DEBE validar que el token de Telegram no sea nulo.` |
| **Evento** | `CUANDO <suceso>, el sistema DEBE <acción>.` | `CUANDO se detecte un cupo en horario de interés, el sistema DEBE enviar una alerta.` |
| **Estado** | `MIENTRAS <condición>, el sistema DEBE <acción>.` | `MIENTRAS el scraper reciba respuestas 429 (Too Many Requests), el sistema DEBE aumentar el intervalo de espera.` |
| **No deseado** | `SI <anomalía> ENTONCES el sistema DEBE <acción>.` | `SI falla la conexión a la API de Colsubsidio ENTONCES el sistema DEBE registrar el error y continuar.` |

## Puerta de Aprobación Humana

*   **Paso 1:** El agente de IA (o el desarrollador) redacta la especificación en `specs/<feature>/`.
*   **Paso 2:** El estado de la feature en `feature_list.json` se mueve a `spec_ready`.
*   **Paso 3:** Se detiene el proceso y se solicita aprobación humana en el chat.
*   **Paso 4:** Con el "aprobado", se cambia el estado a `in_progress` y se escribe el código.
