"""Script para autenticación automatizada con Playwright y extracción de cookies de Colsubsidio."""
from __future__ import annotations

import os
import sys
import json
import base64
import sqlite3
import shutil
import tempfile
import ctypes
from ctypes import wintypes
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    AESGCM = None

try:
    import config
except ImportError:
    config = None

LOGIN_URL = "https://www.diversioncolsubsidio.com/sistema.php/default/loguearSitio"

ENV_KEY_MAP = {
    "sistema": "COLSUBSIDIO_SISTEMA_COOKIE",
    "COLSUBSIDIO_SISTEMA_COOKIE": "COLSUBSIDIO_SISTEMA_COOKIE",
    "Csrf-Token": "COLSUBSIDIO_CSRF_TOKEN",
    "csrf-token": "COLSUBSIDIO_CSRF_TOKEN",
    "CSRF-TOKEN": "COLSUBSIDIO_CSRF_TOKEN",
    "COLSUBSIDIO_CSRF_TOKEN": "COLSUBSIDIO_CSRF_TOKEN",
}

class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char))
    ]

def decrypt_key_with_dpapi(encrypted_key: bytes) -> bytes:
    """Desencripta la clave maestra de Chrome/Edge usando DPAPI de Windows."""
    if encrypted_key.startswith(b"DPAPI"):
        encrypted_key = encrypted_key[5:]

    crypt32 = ctypes.windll.crypt32
    in_blob = DATA_BLOB(len(encrypted_key), ctypes.cast(ctypes.create_string_buffer(encrypted_key), ctypes.POINTER(ctypes.c_char)))
    out_blob = DATA_BLOB()

    success = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob)
    )
    if not success:
        raise OSError("CryptUnprotectData failed. Asegúrate de estar ejecutando el script en la misma cuenta de usuario de Windows.")

    decrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    return decrypted

def decrypt_cookie_value(encrypted_value: bytes, master_key: bytes) -> str:
    """Desencripta el valor de una cookie usando la clave maestra de AES."""
    try:
        if encrypted_value.startswith(b"v10") or encrypted_value.startswith(b"v11"):
            if AESGCM is None:
                return ""
            iv = encrypted_value[3:15]
            ciphertext = encrypted_value[15:]
            aesgcm = AESGCM(master_key)
            decrypted = aesgcm.decrypt(iv, ciphertext, None)
            return decrypted.decode("utf-8")
        return encrypted_value.decode("utf-8")
    except Exception:
        return ""

def get_browser_paths() -> list[dict]:
    """Retorna los directorios de datos de Chrome y Edge en Windows."""
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return []

    return [
        {
            "name": "Google Chrome",
            "user_data_path": os.path.join(local_app_data, "Google", "Chrome", "User Data"),
            "local_state_path": os.path.join(local_app_data, "Google", "Chrome", "User Data", "Local State")
        },
        {
            "name": "Microsoft Edge",
            "user_data_path": os.path.join(local_app_data, "Microsoft", "Edge", "User Data"),
            "local_state_path": os.path.join(local_app_data, "Microsoft", "Edge", "User Data", "Local State")
        }
    ]

def find_cookie_databases(user_data_path: str) -> list[str]:
    """Escanea el directorio de usuario buscando archivos de base de datos de cookies."""
    databases = []
    if not os.path.exists(user_data_path):
        return []

    for root, dirs, files in os.walk(user_data_path):
        if "Cache" in root or "System Profile" in root:
            continue
        for file in files:
            if file == "Cookies":
                if root.endswith("Network") or "Network" in root:
                    databases.append(os.path.join(root, file))
    return databases

def login_and_get_cookies(
    user: str | None = None,
    password: str | None = None,
    headless: bool = True
) -> dict[str, str]:
    """Inicia sesión automáticamente en Colsubsidio usando Playwright Chromium y extrae las cookies de sesión.

    :param user: Usuario o número de documento de Colsubsidio.
    :param password: Contraseña de la cuenta.
    :param headless: Si se ejecuta el navegador en modo sin cabeza (True) o visible (False).
    :return: Diccionario con cookies {"sistema": ..., "Csrf-Token": ...}.
    :raises ValueError: Si no se suministran credenciales.
    :raises RuntimeError: Si el inicio de sesión falla o no se obtienen las cookies.
    """
    if user is not None:
        user_val = str(user)
    else:
        user_val = os.environ.get("COLSUBSIDIO_USER")
        if not user_val and config and hasattr(config, "COLSUBSIDIO_USER"):
            user_val = config.COLSUBSIDIO_USER
        if not user_val:
            user_val = os.environ.get("COLSUBSIDIO_DOCUMENT_NUMBER")
        if not user_val and config and hasattr(config, "COLSUBSIDIO_DOCUMENT_NUMBER"):
            user_val = config.COLSUBSIDIO_DOCUMENT_NUMBER

    if password is not None:
        pass_val = str(password)
    else:
        pass_val = os.environ.get("COLSUBSIDIO_PASS")
        if not pass_val and config and hasattr(config, "COLSUBSIDIO_PASS"):
            pass_val = config.COLSUBSIDIO_PASS

    if not user_val or not pass_val:
        raise ValueError("Las credenciales COLSUBSIDIO_USER y COLSUBSIDIO_PASS son requeridas para el inicio de sesión automático.")

    user_val = str(user_val)
    pass_val = str(pass_val)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("El paquete 'playwright' no está instalado. Instálalo con 'pip install playwright'.")

    headless_bool = False if str(headless).lower() in ("false", "0") else bool(headless)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless_bool)
        context = browser.new_context()
        page = context.new_page()

        page.goto(LOGIN_URL, wait_until="networkidle")

        doc_type = os.environ.get("COLSUBSIDIO_DOCUMENT_TYPE")
        if not doc_type and config and hasattr(config, "COLSUBSIDIO_DOCUMENT_TYPE"):
            doc_type = config.COLSUBSIDIO_DOCUMENT_TYPE
        if not doc_type:
            doc_type = "CC"

        # Seleccionar tipo de documento si existe el campo
        if page.query_selector('select[name="tipo_documento"]'):
            page.select_option('select[name="tipo_documento"]', doc_type)
        elif page.query_selector('#tipo_documento'):
            page.select_option('#tipo_documento', doc_type)

        # Rellenar usuario / documento
        user_sel = None
        for sel in ['input[name="documento"]', 'input[name="usuario"]', 'input[name="user"]', '#documento', '#usuario', 'input[type="text"]']:
            if page.query_selector(sel):
                user_sel = sel
                break
        if user_sel:
            page.fill(user_sel, user_val)

        # Rellenar clave / contraseña
        pass_sel = None
        for sel in ['input[name="clave"]', 'input[name="password"]', 'input[name="pass"]', '#clave', '#password', 'input[type="password"]']:
            if page.query_selector(sel):
                pass_sel = sel
                break
        if pass_sel:
            page.fill(pass_sel, pass_val)

        # Enviar formulario
        submit_sel = None
        for sel in ['button[type="submit"]', 'input[type="submit"]', '#btnIngresar', '#btn-ingresar', 'form button']:
            if page.query_selector(sel):
                submit_sel = sel
                break

        if submit_sel:
            page.click(submit_sel)
            page.wait_for_load_state("networkidle")
        elif user_sel and pass_sel:
            page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle")

        cookies_list = context.cookies()
        browser.close()

    extracted = {}
    for c in cookies_list:
        name = c.get("name", "")
        if name == "sistema":
            extracted["sistema"] = c.get("value", "")
        elif name in ("Csrf-Token", "csrf-token", "CSRF-TOKEN"):
            extracted["Csrf-Token"] = c.get("value", "")

    if "sistema" in extracted and "Csrf-Token" in extracted:
        update_env_file(extracted)
        os.environ["COLSUBSIDIO_SISTEMA_COOKIE"] = extracted["sistema"]
        os.environ["COLSUBSIDIO_CSRF_TOKEN"] = extracted["Csrf-Token"]
        if config:
            config.COLSUBSIDIO_SISTEMA_COOKIE = extracted["sistema"]
            config.COLSUBSIDIO_CSRF_TOKEN = extracted["Csrf-Token"]
        return extracted
    else:
        raise RuntimeError("No se pudieron obtener las cookies 'sistema' y 'Csrf-Token' (credenciales inválidas o error de inicio de sesión).")

def extract_local_browser_cookies() -> dict[str, str]:
    """Extrae las cookies sistema y Csrf-Token de las bases de datos locales de Chrome y Edge en Windows."""
    extracted = {}
    if sys.platform != "win32":
        return extracted

    for browser in get_browser_paths():
        if not os.path.exists(browser["local_state_path"]):
            continue

        print(f"Buscando cookies en {browser['name']}...")
        try:
            with open(browser["local_state_path"], "r", encoding="utf-8") as f:
                local_state = json.load(f)
            encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
            encrypted_key = base64.b64decode(encrypted_key_b64)
            master_key = decrypt_key_with_dpapi(encrypted_key)
        except Exception as e:
            print(f"  No se pudo leer la clave maestra de {browser['name']}: {e}")
            continue

        cookie_dbs = find_cookie_databases(browser["user_data_path"])
        for db_path in cookie_dbs:
            fd, temp_db = tempfile.mkstemp(suffix=".sqlite")
            os.close(fd)
            try:
                shutil.copyfile(db_path, temp_db)
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%diversioncolsubsidio.com'"
                )
                for name, encrypted_value in cursor.fetchall():
                    decrypted = decrypt_cookie_value(encrypted_value, master_key)
                    if decrypted:
                        if name == "sistema":
                            extracted["sistema"] = decrypted
                        elif name == "Csrf-Token":
                            extracted["Csrf-Token"] = decrypted
                conn.close()
            except Exception as e:
                print(f"  [Aviso] No se pudo leer {db_path}: {e}")
            finally:
                if os.path.exists(temp_db):
                    try:
                        os.remove(temp_db)
                    except Exception:
                        pass

            if "sistema" in extracted and "Csrf-Token" in extracted:
                print(f"  Cookies encontradas con éxito en {browser['name']}!")
                return extracted

    return extracted

def extract_colsubsidio_cookies() -> dict[str, str]:
    """Extrae las cookies sistema y Csrf-Token de Colsubsidio.

    Intenta primero el login automático vía Playwright Chromium (`login_and_get_cookies`).
    Si falla o no hay credenciales, y se ejecuta en Windows, recurre a la extracción local
    de cookies del navegador Chrome/Edge.
    """
    try:
        return login_and_get_cookies()
    except Exception as e:
        print(f"[Aviso] No se pudo realizar el inicio de sesión automático con Playwright: {e}")

    if sys.platform == "win32":
        print("[Info] Intentando extracción de cookies desde el navegador local...")
        try:
            return extract_local_browser_cookies()
        except Exception as ex:
            print(f"[Error] Falló la extracción local de cookies: {ex}")

    return {}

def update_env_file(cookies: dict[str, str], env_path: str | None = None) -> bool:
    """Actualiza el archivo .env local con los nuevos valores de cookies de forma atómica y segura."""
    if env_path is None:
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")

    env_path = os.path.abspath(env_path)
    env_dir = os.path.dirname(env_path)
    if not os.path.exists(env_dir):
        return False

    updates_to_make = {}
    for k, v in cookies.items():
        if v is None:
            continue
        clean_v = str(v).replace("\r", "").replace("\n", "")
        if clean_v == "":
            continue
        env_k = ENV_KEY_MAP.get(k, k)
        updates_to_make[env_k] = clean_v

    lines = []
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            lines = []

    try:
        new_lines = []
        updated_keys = set()

        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in line:
                key_part, _, _ = line.partition("=")
                key_name = key_part.strip()
                if key_name in updates_to_make:
                    new_lines.append(f"{key_name}={updates_to_make[key_name]}\n")
                    updated_keys.add(key_name)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        for key_name, val in updates_to_make.items():
            if key_name not in updated_keys:
                if new_lines and not new_lines[-1].endswith("\n"):
                    new_lines[-1] += "\n"
                new_lines.append(f"{key_name}={val}\n")

        fd, temp_path = tempfile.mkstemp(dir=env_dir, prefix=".env_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", errors="replace") as f:
                f.writelines(new_lines)
            os.replace(temp_path, env_path)
            return True
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise
    except Exception as e:
        print(f"Error al escribir en .env: {e}")
        return False

def sync_secrets_to_github(cookies: dict[str, str]) -> bool:
    """Intenta sincronizar los secretos de GitHub usando la herramienta oficial gh CLI."""
    import subprocess
    try:
        result = subprocess.run(["gh", "auth", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            return False

        print("\nSincronizando cookies con los secretos de GitHub usando gh CLI...")
        
        subprocess.run(
            ["gh", "secret", "set", "COLSUBSIDIO_SISTEMA_COOKIE", "--body", cookies["sistema"]],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
        
        subprocess.run(
            ["gh", "secret", "set", "COLSUBSIDIO_CSRF_TOKEN", "--body", cookies["Csrf-Token"]],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
        
        print("Sincronización de secretos en GitHub completada con éxito.")
        return True
    except Exception as e:
        print(f"No se pudieron sincronizar las cookies en GitHub: {e}")
        return False

def main():
    print("=== Extractor Automatizado de Cookies de Colsubsidio ===")
    
    if sys.platform == "win32":
        print("Liberando archivos de cookies (cerrando procesos Edge/Chrome en segundo plano si los hay)...")
        import subprocess
        subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    cookies = extract_colsubsidio_cookies()

    if "sistema" in cookies and "Csrf-Token" in cookies:
        print("\n[RESULTADOS ENCONTRADOS]")
        print(f"sistema cookie captured (len={len(cookies['sistema'])})")
        print(f"Csrf-Token cookie captured (len={len(cookies['Csrf-Token'])})")
        
        if update_env_file(cookies):
            print("\n[OK] El archivo .env local ha sido actualizado automáticamente con los nuevos valores.")
            print("Ya puedes ejecutar el Revisor localmente y usará estas cookies.")
        else:
            print("\n[WARNING] Las cookies se extrajeron pero no se pudo actualizar el archivo .env.")

        if not sync_secrets_to_github(cookies):
            print("\n[INFO] Sincronización automática con GitHub omitida (gh CLI no instalado o no autenticado).")
    else:
        print("\n[ERROR] No se encontraron cookies activas de diversioncolsubsidio.com.")
        print("Asegúrate de configurar COLSUBSIDIO_USER y COLSUBSIDIO_PASS en tu entorno o archivo .env.")
        sys.exit(1)

if __name__ == "__main__":
    main()
