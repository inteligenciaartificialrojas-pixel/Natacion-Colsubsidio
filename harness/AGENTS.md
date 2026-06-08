# AGENTS.md — Mapa de navegación para agentes de IA en el Revisor de Natación Colsubsidio

> Este archivo es el **punto de entrada** para cualquier agente que trabaje en este
> repositorio. Describe la estructura, reglas y flujo de desarrollo del Revisor de Natación.

---

## 1. Antes de empezar (obligatorio)

1. Sitúate en la raíz del arnés (`g:/Mi unidad/Natacion Colsubsidio/harness/`).
2. Ejecuta `./init.sh` (o `.\init.ps1` en Windows) y verifica que termina sin errores.
3. Lee `progress/current.md` para entender el estado de la sesión de desarrollo activa.
4. Lee `feature_list.json`. Toda feature nueva (`"sdd": true`) pasa por **Spec Driven Development** (ver `docs/specs.md`).

## 2. Estructura del Repositorio

El arnés se ejecuta desde `harness/`, pero la lógica del código reside en `../code/`.

| Archivo / carpeta            | Qué contiene                                                                | Cuándo leerlo |
|------------------------------|-----------------------------------------------------------------------------|---------------|
| `feature_list.json`          | Lista de tareas con estado (`pending` / `spec_ready` / `in_progress` / `done`) | Al empezar |
| `progress/current.md`        | Estado de la sesión actual                                                  | Al empezar |
| `progress/history.md`        | Bitácora histórica de sesiones anteriores                                   | Para ver contexto histórico |
| `specs/<feature>/`           | `requirements.md` (EARS) + `design.md` + `tasks.md`                        | Antes de implementar |
| `docs/architecture.md`       | Especificación de la arquitectura del revisor (scraper, notifier, config, main) | Antes de diseñar/implementar |
| `docs/conventions.md`        | Convenciones de nomenclatura y estilo PEP 8                                 | Antes de escribir código |
| `docs/specs.md`              | Metodología de Spec Driven Development                                      | Antes de redactar un spec |
| `docs/verification.md`       | Cómo verificar el funcionamiento con pytest y mocks                         | Antes de dar por terminada una tarea |
| `CHECKPOINTS.md`             | Criterios objetivos de evaluación final                                      | Para auto-evaluación |
| `../code/`                   | Código fuente principal (config, notifier, scraper, main)                   | Para programar |
| `tests/`                     | Pruebas automáticas locales                                                 | Para verificar |

## 3. Reglas de Oro del Revisor de Natación
Cualquier código que altere la lógica de monitoreo debe respetar:
*   **Regla 1: EFICIENCIA (Cortesía y Antiban):** Las peticiones a la web de Colsubsidio deben hacerse con intervalos prudentes y headers válidos para evitar bloqueos por IP o saturación de su infraestructura.
*   **Regla 2: ROBUSTEZ (Resiliencia ante fallos):** Caídas de red, problemas temporales con el bot de Telegram o cambios menores en el JSON/DOM de Colsubsidio no deben colapsar el programa principal; deben ser reportadas en el log y el ciclo debe reintentarse.
*   **Regla 3: SILENCIO (No Spam):** No se deben enviar notificaciones repetidas sobre el mismo cupo disponible. El sistema debe mantener una caché/historial reciente de cupos ya alertados para no saturar al usuario.

## 4. Flujo de Trabajo (SDD)
El desarrollo de features sigue el siguiente ciclo secuencial controlado:
```
pending → [redacción del spec] → spec_ready → ⏸ ESPERA APROBACIÓN HUMANA → in_progress → [implementación + tests] → done
```
*   El humano debe validar el diseño de la feature en `specs/<feature>/` antes de avanzar de `spec_ready` a `in_progress`.
