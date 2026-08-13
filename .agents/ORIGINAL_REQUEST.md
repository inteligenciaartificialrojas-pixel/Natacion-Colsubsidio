# Original User Request

## 2026-08-09T18:17:56Z

Automate session login using Playwright and make the Colsubsidio Swimming availability checking workflow fully self-healing and resilient against session expiration.

Working directory: `i:/Mi unidad/Natacion Colsubsidio`
Integrity mode: development

## Requirements

### R1. Automated Playwright Login & Session Renewal
Implement a Playwright-based headless browser login module in Python that automates the login flow on Colsubsidio (`https://www.diversioncolsubsidio.com/sistema.php/default/loguearSitio`) using credentials `COLSUBSIDIO_USER` and `COLSUBSIDIO_PASS` from environment variables.
When `scraper.py` detects an HTTP 401 Unauthorized or expired session, automatically invoke Playwright to perform login, capture fresh `sistema` and `Csrf-Token` cookies, update `.env` (and session headers in memory), and retry the failed API request seamlessly.

### R2. CI/CD & Local Runner Compatibility
Update `code/requirements.txt`, `.env.example`, and `.github/workflows/check.yml` to install Playwright dependencies (`playwright` and `playwright install chromium`), ensuring that both local execution and scheduled GitHub Actions runs automatically renew sessions without crashing with exit code 1.

### R3. Preserved Business Logic & Notifications
Preserve all existing scraper features: filtering preferred venue schedules (El Cubo, Plaza de las Américas, Club La Colina), checking weekday/weekend rules, sending Telegram notifications, handling state caching (`.cooldown_state`, `.last_slots.json`), and interactive Telegram reservation commands.

## Acceptance Criteria

### Automated Login & Recovery
- [ ] An automated login helper using Playwright launches headless Chromium, authenticates using `COLSUBSIDIO_USER` and `COLSUBSIDIO_PASS`, and extracts valid `sistema` & `Csrf-Token` cookies.
- [ ] `scraper.py` catches `SessionExpiredException` / HTTP 401, triggers Playwright session renewal, updates session cookies in memory and in `.env`, and successfully retries the request without failing the process.

### GitHub Actions & Execution
- [ ] Running `python code/main.py --once` in an environment with expired or missing cookies successfully logs in via Playwright, fetches availability, and completes with exit code 0.
- [ ] GitHub Actions workflow `.github/workflows/check.yml` installs Playwright and Chromium dependencies and runs `main.py` without exit code 1 errors.

### Integrity & Quality
- [ ] Automated tests or verification scripts confirm that expired cookie scenarios automatically recover and fetch availability.
- [ ] No regression in Telegram notifications or slot filtering logic.

## 2026-08-12T04:36:38Z

Monitor automatizado de disponibilidad de natación de Colsubsidio desplegado en GitHub Actions con Cronjob (cada 20 minutos), que consulta exclusivamente los cupos libres en la ventana horaria de preferencia del usuario y notifica a Telegram de forma limpia y sin duplicados.

Working directory: j:\Mi unidad\Natacion Colsubsidio
Integrity mode: demo

## Technical Findings (Page & API Analysis)
- La página web (https://www.diversioncolsubsidio.com/deportes-practica-libre-natacion#/wizard?producto=80) utiliza AngularJS y llama a las APIs de backend:
  - `/v1/centro_entrenamiento/{id}/practicalibre/calendario`
  - `/v1/centro_entrenamiento/{id}/practicalibre/disponibilidad?filtrarSinCupo=0`
- **Autenticación requerida por la API:** Colsubsidio exige cookies de sesión válidas (`sistema` y `Csrf-Token`) para responder a las consultas de disponibilidad (las peticiones anónimas retornan `HTTP 401 Unauthorized`).
- **Alcance ajustado:** No se realizará ninguna acción de reserva ni consumo de tiquetera. Únicamente se mantendrán las credenciales/cookies de sesión necesarias en GitHub Secrets (`COLSUBSIDIO_SISTEMA_COOKIE`, `COLSUBSIDIO_CSRF_TOKEN`) para habilitar la lectura de horarios y cupos.

## Requirements

### R1. Availability API Scraper & Cookie Session Handling
Reconstruir el scraper para consultar únicamente la disponibilidad de fechas y cupos por sede mediante los endpoints REST (`/v1/centro_entrenamiento/.../practicalibre/calendario` y `disponibilidad`), manejando limpiamente las cookies de sesión para la consulta de datos sin ejecutar acciones de reserva.

### R2. Strict Schedule Filter Engine
Filtrar la oferta de cupos libres para notificar exclusivamente aquellos que coincidan con la ventana deseada por el usuario:
- **Lunes a Viernes:** turnos antes de las 7:00 AM o después de las 5:00 PM (17:00).
- **Sábados y Domingos:** cualquier hora del día.

### R3. Clean Telegram Notifications & Deduplication
Enviar mensajes limpios, simples, cortos y estructurados a Telegram (Fecha, Hora, Sede/Piscina y Cupos Libres). Mantener estado persistente entre ejecuciones para evitar enviar notificaciones duplicadas de cupos ya reportados.

### R4. GitHub Actions CI/CD Cron Automation
Configurar la automatización en `.github/workflows/check.yml` para ejecutar la verificación cada 20 minutos vía Cronjob, utilizando GitHub Secrets para almacenar `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `COLSUBSIDIO_SISTEMA_COOKIE` y `COLSUBSIDIO_CSRF_TOKEN`.

## Acceptance Criteria

### Core Functionality
- [ ] Código simplificado: removida toda lógica de reservación de turnos y manejo de tiqueteras.
- [ ] Consulta eficiente a los endpoints de disponibilidad usando la cookie de sesión configurada.
- [ ] Filtro estricto de horarios aplicado correctamente (L-V < 7am ó > 5pm; S-D 24h).
- [ ] Mensaje de Telegram claro y conciso, previniendo alertas repetidas de los mismos horarios.

### Automation & Deployment
- [ ] Workflow `.github/workflows/check.yml` actualizado y validado para ejecuciones periódicas de 20 min y despacho manual (`workflow_dispatch`).
- [ ] Guía paso a paso en el README sobre cómo obtener y renovar fácilmente las cookies desde las herramientas de desarrollador del navegador cuando expiren.
