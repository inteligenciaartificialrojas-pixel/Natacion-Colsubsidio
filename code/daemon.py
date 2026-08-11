"""Daemon para sincronización automática en segundo plano de cookies de Colsubsidio a GitHub Secrets."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

# Asegurar que el directorio raíz del proyecto esté en sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
code_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from get_cookies import extract_colsubsidio_cookies, update_env_file, sync_secrets_to_github

# Configurar logging en archivo daemon.log y consola
log_file = os.path.join(root_dir, "daemon.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("colsubsidio_daemon")

def run_daemon_sync() -> bool:
    """Ejecuta la extracción de cookies y la sincronización con GitHub Secrets."""
    logger.info("=== Iniciando sincronización automática del daemon de Colsubsidio ===")
    try:
        cookies = extract_colsubsidio_cookies()
        if "sistema" in cookies and "Csrf-Token" in cookies:
            logger.info("Cookies 'sistema' y 'Csrf-Token' obtenidas con éxito.")
            
            # 1. Actualizar .env local
            if update_env_file(cookies):
                logger.info("Archivo .env local actualizado correctamente.")
            else:
                logger.warning("No se pudo actualizar el archivo .env local.")

            # 2. Sincronizar secretos con GitHub Secrets
            if sync_secrets_to_github(cookies):
                logger.info("Secretos de GitHub (COLSUBSIDIO_SISTEMA_COOKIE y COLSUBSIDIO_CSRF_TOKEN) sincronizados con éxito.")
                return True
            else:
                logger.info("No se completó la sincronización con GitHub (gh CLI no instalado o no autenticado).")
                return True
        else:
            logger.error("No se pudieron obtener cookies de sesión válidas.")
            return False
    except Exception as e:
        logger.error("Error imprevisto durante la ejecución del daemon: %s", e)
        return False

if __name__ == "__main__":
    success = run_daemon_sync()
    sys.exit(0 if success else 1)
