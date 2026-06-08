# Arnés de Spec Driven Development (SDD) para BITS

Este subdirectorio contiene el arnés de gobernanza y control diseñado para implementar **Spec Driven Development (SDD)** en el proyecto BITS.

> El pipeline principal de BITS se localiza en `../code/` y sus diccionarios en `../data/`. El arnés reside de forma aislada en este directorio para gobernar los ciclos de desarrollo y garantizar la inalterabilidad de la calidad de datos y las reglas del pipeline.

---

## Estructura del Arnés

El arnés se organiza bajo cuatro pilares metodológicos:

| Pilar                                  | Manifestación en este Arnés                                                       |
|----------------------------------------|-----------------------------------------------------------------------------------|
| **1. El repositorio ES el sistema**    | `AGENTS.md`, `init.ps1` / `init.sh`, `feature_list.json`, `docs/`, `progress/`    |
| **2. Orquestación multi-agente**       | `.agents/agents/leader.md`, `spec_author.md`, `implementer.md`, `reviewer.md`     |
| **3. Spec Driven Development**         | `docs/specs.md`, requirements en notación EARS estricta, puerta de aprobación     |
| **4. Supervisión y calidad**           | `CHECKPOINTS.md`, pruebas unitarias bajo `pytest` en `tests/`                      |

---

## Cómo empezar (Desarrolladores e IA)

Antes de abrir una sesión de desarrollo o delegar tareas a agentes, sitúate en la carpeta `harness/` y ejecuta el script de inicialización para comprobar la salud del entorno:

### En Windows (PowerShell):
```powershell
powershell -ExecutionPolicy Bypass -File .\init.ps1
```

### En Unix/macOS (Bash):
```bash
./init.sh
```

Si todo termina en verde (`[OK]`), el entorno de BITS está listo y los tests de cordura han verificado correctamente la importación de todas las fases del pipeline.

---

## Ciclo de Vida del Desarrollo (SDD)

El flujo de adición de nuevas features o refactorizaciones se gestiona mediante el agente `leader` en base al archivo `feature_list.json`:

```
pending → [spec_author] → spec_ready → ⏸ HUMANO APRUEBA → in_progress → [implementer → reviewer] → done
```

1. **Fase de Spec (`pending` -> `spec_ready`):**
   - El agente `spec_author` redacta el diseño, checklist de tareas y requisitos en notación EARS estricta en `specs/<feature-name>/{requirements,design,tasks}.md`.
   - El flujo se detiene en `spec_ready` solicitando la **aprobación humana** explícita del diseño en chat.

2. **Fase de Implementación y Revisión (`in_progress` -> `done`):**
   - El agente `implementer` codifica la lógica en `../code/` y crea las pruebas correspondientes en `tests/` bajo `pytest`, marcando el checklist en `tasks.md`.
   - El agente `reviewer` comprueba de forma automática y estricta que cada requisito cuente con cobertura en pytest y que se respeten las **3 Reglas de Oro de BITS**.

---

## Mapa de Documentación del Arnés

- [AGENTS.md](file:///g:/Mi%20unidad/BITS/harness/AGENTS.md) — Punto de entrada y mapa del repositorio para la IA.
- [CHECKPOINTS.md](file:///g:/Mi%20unidad/BITS/harness/CHECKPOINTS.md) — Criterios objetivos que evalúan la calidad al cerrar una sesión.
- [docs/architecture.md](file:///g:/Mi%20unidad/BITS/harness/docs/architecture.md) — Especificaciones de arquitectura de las 8 fases de BITS y el pipeline.
- [docs/conventions.md](file:///g:/Mi%20unidad/BITS/harness/docs/conventions.md) — Convenciones de nomenclatura y estilo PEP 8.
- [docs/specs.md](file:///g:/Mi%20unidad/BITS/harness/docs/specs.md) — Metodología detallada de redacción en EARS y SDD.
- [docs/verification.md](file:///g:/Mi%20unidad/BITS/harness/docs/verification.md) — Guías para realizar pruebas rigurosas utilizando `pytest`.
