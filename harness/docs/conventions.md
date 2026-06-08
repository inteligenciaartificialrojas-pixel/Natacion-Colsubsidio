# Convenciones de Código (Revisor de Natación)

Este documento define el estándar de estilo y nomenclatura para el proyecto.

## Estilo de Programación (Python 3.10+)

- **Estilo:** PEP 8.
- **Ancho máximo de línea:** 100 caracteres.
- **Comillas:** Dobles (`"..."`) por defecto. Comillas simples (`'...'`) se usan cuando sea necesario evitar escapes internos.
- **Tipado estático:** Se prefiere el uso de anotaciones de tipo (`def notify(slots: list[dict]) -> bool:`).
- **Manejo de dependencias:** Declarar cualquier librería externa (ej: `httpx`, `pytest`) en un archivo `requirements.txt`.

## Nomenclatura

- **Archivos de Código:** `snake_case` en inglés (ej: `scraper.py`, `notifier.py`).
- **Clases:** `PascalCase` (ej: `TelegramNotifier`, `ColsubsidioScraper`).
- **Funciones y Variables:** `snake_case` (ej: `fetch_slots`, `filter_slots`, `token`).
- **Constantes:** `UPPER_SNAKE` (ej: `DEFAULT_CHECK_INTERVAL_SECONDS`).

## Control de Errores y Logs

- Se prohíbe el uso de `print()` directos en el código principal; usar la librería estándar `logging` configurada a nivel del orquestador.
- Las fallas de red del Scraper o Notifier no deben propagarse hasta matar el loop principal. Deben ser atrapadas (ej: `try/except Exception`) e informadas con un log de advertencia (`logger.warning`), permitiendo que el siguiente ciclo se intente tras el intervalo de espera.
