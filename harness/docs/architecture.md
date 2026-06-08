# Arquitectura del Revisor de Natación Colsubsidio

Este documento define la arquitectura de software y el flujo de datos del revisor periódico de práctica libre.

---

## 1. Diseño de Capas

El proyecto está diseñado bajo un modelo modular simple y desacoplado:

```
                  ┌──────────────────────┐
                  │      Config          │
                  │   (code/config.py)   │
                  └──────────┬───────────┘
                             │
                             ▼
┌──────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│   Scraper    ├──►  Orquestador / Loop  ├──►      Notifier        │
│(code/scraper.py)│  │   (code/main.py)   │  │ (code/notifier.py)   │
└──────────────┘  └──────────────────────┘  └──────────┬───────────┘
                                                       │
                                                       ▼
                                             ┌───────────────────┐
                                             │   Telegram Bot    │
                                             └───────────────────┘
```

1.  **Capa de Configuración (`code/config.py`):**
    *   Lee tokens de Telegram y Chat ID desde variables de entorno.
    *   Define las sedes autorizadas (El Cubo y Plaza Américas).
    *   Define los horarios de interés para la natación.
    *   Establece el intervalo del bucle (ej: cada 5 minutos).

2.  **Capa de Extracción (`code/scraper.py`):**
    *   Simula la llamada HTTP a la API de la tienda de diversión de Colsubsidio.
    *   Procesa y estandariza los horarios disponibles y el número de cupos.
    *   Maneja de forma segura las excepciones en caso de que el sitio de Colsubsidio esté caído o cambie sus respuestas JSON.

3.  **Capa de Notificación (`code/notifier.py`):**
    *   Se encarga de dar formato Markdown al mensaje de alerta.
    *   Realiza el envío al bot de Telegram.
    *   Mantiene una caché en memoria (o base de datos simple) de alertas recientes para evitar enviar mensajes duplicados sobre el mismo cupo.

4.  **Capa de Orquestación (`code/main.py`):**
    *   Contiene el bucle principal de ejecución.
    *   Aplica las reglas de filtrado de sedes y de horarios:
        *   **Lunes a Viernes:** Alerta solo si la hora de inicio de la natación está en el rango `[18:00, 20:00]` (6:00 PM a 8:00 PM).
        *   **Sábado y Domingo:** Alerta para cualquier horario.

---

## 2. Reglas de Oro Técnicas

*   **Regla 1: EFICIENCIA (Cortesía y Antiban):** Las peticiones a la web de Colsubsidio deben hacerse con intervalos prudentes y headers válidos para evitar bloqueos por IP o saturación de su infraestructura.
*   **Regla 2: ROBUSTEZ (Resiliencia ante fallos):** Caídas de red, problemas temporales con el bot de Telegram o cambios menores en el JSON/DOM de Colsubsidio no deben colapsar el programa principal; deben ser reportadas en el log y el ciclo debe reintentarse.
*   **Regla 3: SILENCIO (No Spam):** No se deben enviar notificaciones repetidas sobre el mismo cupo disponible. El sistema debe mantener una caché/historial reciente de cupos ya alertados para no saturar al usuario.
