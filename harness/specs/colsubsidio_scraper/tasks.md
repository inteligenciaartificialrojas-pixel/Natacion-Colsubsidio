# Tareas de Desarrollo: Scraper de Colsubsidio (`colsubsidio_scraper`)

Lista de tareas para el desarrollo y verificación del extractor de disponibilidad.

---

## Checklist de Desarrollo

- [x] **T1 — Mapeo de Identificadores:**
      Actualizar [config.py](file:///g:/Mi%20unidad/Natacion%20Colsubsidio/code/config.py) con el diccionario que mapea los nombres de las sedes con sus correspondientes IDs de servicio.
      *Cubre: R1.*

- [x] **T2 — Lógica de Extracción (Scraper):**
      Crear [scraper.py](file:///g:/Mi%20unidad/Natacion%20Colsubsidio/code/scraper.py) con la clase `ColsubsidioScraper`, excepciones personalizadas (`SessionExpiredException`), y lógica de POST para obtener calendario y horarios con cupos.
      *Cubre: R1, R2, R3, R4, R5.*

- [x] **T3 — Pruebas Unitarias:**
      Escribir `harness/tests/test_scraper.py` para verificar que el scraper extraiga correctamente las fechas e identifique cupos a partir de respuestas JSON mockeadas, y valide el manejo de excepciones de sesión expirada (401) y errores de conexión.
      *Cubre: R2, R3, R4, R5.*
