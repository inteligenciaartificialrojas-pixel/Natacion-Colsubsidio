# Diseño Técnico: Scraper de Colsubsidio (`colsubsidio_scraper`)

Este documento detalla el diseño técnico para interactuar con la API privada de Colsubsidio.

---

## 1. Mapeo de Sedes y Servicios

Para natación en las sedes preferidas, los identificadores de servicio (`idServicio`) son:
*   **El Cubo:** `232` (Práctica libre natación El Cubo)
*   **Plaza de las Américas:** `428` (Práctica libre de natación Bloc Plaza de las Américas)

Estos IDs serán almacenados en `code/config.py`.

---

## 2. Clase `ColsubsidioScraper`

El código se implementará en [scraper.py](file:///g:/Mi%20unidad/Natacion%20Colsubsidio/code/scraper.py).

```python
class SessionExpiredException(Exception):
    """Excepción lanzada cuando la sesión de Colsubsidio (cookie 'sistema') ha expirado."""
    pass

class ColsubsidioScraper:
    def __init__(self, session_cookie: str | None = None, csrf_token: str | None = None) -> None:
        """
        Inicializa el scraper con las cookies necesarias.
        Si no se suministran, se leen de config.py.
        """
        self.session = requests.Session()
        # Configurar cookies
        cookie_val = session_cookie or os.environ.get("COLSUBSIDIO_SISTEMA_COOKIE")
        csrf_val = csrf_token or os.environ.get("COLSUBSIDIO_CSRF_TOKEN")
        
        if cookie_val:
            self.session.cookies.set("sistema", cookie_val)
        if csrf_val:
            self.session.cookies.set("Csrf-Token", csrf_val)
            
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

    def fetch_available_dates(self, service_id: int) -> list[str]:
        """
        Realiza la petición POST a /v1/centro_entrenamiento/{id}/practicalibre/calendario.
        Filtra y retorna fechas donde 'disponibilidad' sea True.
        """
        # ...

    def fetch_slots_for_date(self, service_id: int, date_str: str) -> list[dict]:
        """
        Realiza la petición POST a /v1/centro_entrenamiento/{id}/practicalibre/disponibilidad.
        Procesa los horarios de la respuesta y retorna una lista de diccionarios de cupos.
        """
        # ...
```

---

## 3. Estructura de Endpoints y Payloads

### A. Obtención de Fechas (Calendario)
*   **URL:** `https://www.diversioncolsubsidio.com/v1/centro_entrenamiento/{service_id}/practicalibre/calendario`
*   **Método:** `POST`
*   **Payload:**
    ```json
    {
      "filtro_disponibilidad": {
        "fecha_inicio": "YYYY-MM-DD",
        "fecha_fin": "YYYY-MM-DD",
        "inicio_inmediato": false
      }
    }
    ```
*   **Respuesta Exitosa (200 JSON):**
    ```json
    {
      "fechas": {
        "2026-06-10": {
          "fecha": "2026-06-10",
          "disponibilidad": true
        }
      }
    }
    ```

### B. Obtención de Horarios y Cupos (Disponibilidad)
*   **URL:** `https://www.diversioncolsubsidio.com/v1/centro_entrenamiento/{service_id}/practicalibre/disponibilidad?filtrarSinCupo=0`
*   **Método:** `POST`
*   **Payload:**
    ```json
    {
      "filtro_disponibilidad": {
        "fecha_inicio": "YYYY-MM-DD",
        "fecha_fin": "YYYY-MM-DD",
        "inicio_inmediato": false
      },
      "turno_practica_libre": {
        "cantidad_usos": 1,
        "numero_participantes": 1,
        "persona": []
      }
    }
    ```
*   **Respuesta Exitosa (200 JSON):**
    Retorna un listado de horarios con sus zonas y cupos disponibles:
    ```json
    {
      "horarios": [
        {
          "horario": {
            "hora_inicio": "18:00:00"
          },
          "duracion": 50,
          "zonas": [
            {
              "capacidad_disponible": 3
            }
          ]
        }
      ]
    }
    ```
    *Cálculo de cupos:* Suma de `capacidad_disponible` de todas las zonas del horario.

---

## 4. Alternativas Descartadas

*   **Alternativa Descartada: Web Scraping con Playwright (Headless)**
    *   *Razón:* Como el usuario seleccionó la opción de API y queremos mantener el bot liviano y ejecutable en entornos de bajos recursos (ej. nubes gratis), el uso de `requests` con la cookie de sesión del navegador es más ágil y consume 99% menos RAM que levantar navegadores Chromium.
