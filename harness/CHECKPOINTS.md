# CHECKPOINTS — Evaluación del Estado Final (Revisor de Natación)

> Lista de puntos de control objetivos que determinan si el desarrollo está en un estado sano.

## C1 — Estructura e Integridad del Arnés
- [ ] Existen los documentos principales: `AGENTS.md`, `CHECKPOINTS.md`, `feature_list.json`, `progress/current.md`.
- [ ] Existen las guías metodológicas en `docs/`: `architecture.md`, `conventions.md`, `specs.md`, `verification.md`.
- [ ] `./init.sh` (o `init.ps1`) se ejecuta con éxito (exit code 0).

## C2 — Coherencia de Estados
- [ ] Como máximo una sola feature en estado `in_progress` al mismo tiempo.
- [ ] Las features marcadas como `done` tienen pruebas en `tests/` que pasan al 100%.
- [ ] `progress/current.md` contiene el log de la sesión activa, e `history.md` registra las pasadas.

## C3 — Calidad de la Lógica y Arquitectura
- [ ] La configuración en `code/config.py` lee variables de entorno y tiene valores por defecto sanos.
- [ ] El notificador (`code/notifier.py`) implementa la lógica de de-duplicación para no reenviar alertas repetidas.
- [ ] El scraper (`code/scraper.py`) maneja excepciones de red y responde correctamente a las respuestas de la API de Colsubsidio.
- [ ] El orquestador (`code/main.py`) respeta las reglas de filtrado de sedes (El Cubo, Plaza Américas) y horarios (L-V 6-8 PM, S-D libre).
- [ ] No existen dependencias externas no declaradas en un archivo `requirements.txt` o `pyproject.toml`.
- [ ] No hay `print()` sueltos para debug; se utiliza el módulo nativo `logging` de Python.

## C4 — Rigor de las Pruebas (Pytest)
- [ ] Los tests se encuentran en `tests/` y corren bajo `pytest`.
- [ ] Se utilizan fixtures y mocks para simular las llamadas HTTP tanto a Colsubsidio como a Telegram (evitando llamadas reales durante las pruebas unitarias).
- [ ] La cobertura de pruebas cubre al menos el 80% de la lógica del código en `code/`.

## C5 — Cierre de Sesión Limpio
- [ ] El repositorio queda limpio sin archivos temporales, bases de datos sqlite locales temporales u hojas de cálculo fuera de `.gitignore`.
- [ ] La feature finalizada se marca como `done` y se documenta en el historial.
- [ ] Se actualiza la documentación del proyecto con instrucciones de inicio rápido.
