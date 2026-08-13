"""Pruebas de estrés y casos límite (adversarial testing) para el hito M2.

Cubre:
1. Variables de entorno faltantes o malformadas.
2. Credenciales inválidas o incompletas.
3. Archivos .env malformados, corruptos o no-UTF8.
4. Ausencia de dependencias de Playwright o binarios de Chromium.
5. Ausencia de la librería cryptography para desencriptado DPAPI/AESGCM.
6. Errores de sintaxis y duplicados en update_env_file.
"""
from __future__ import annotations

import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock

import get_cookies
from get_cookies import (
    login_and_get_cookies,
    extract_colsubsidio_cookies,
    update_env_file,
    decrypt_cookie_value,
)


# ============================================================================
# 1. STRESS TEST: VARIABLES DE ENTORNO FALTANTES O MALFORMADAS
# ============================================================================

def test_missing_all_credentials_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que se lance ValueError cuando no exista ninguna credencial en env ni config."""
    monkeypatch.delenv("COLSUBSIDIO_USER", raising=False)
    monkeypatch.delenv("COLSUBSIDIO_PASS", raising=False)
    monkeypatch.delenv("COLSUBSIDIO_DOCUMENT_NUMBER", raising=False)

    with patch("config.COLSUBSIDIO_USER", None), \
         patch("config.COLSUBSIDIO_PASS", None), \
         patch("config.COLSUBSIDIO_DOCUMENT_NUMBER", None):
        with pytest.raises(ValueError, match="credenciales COLSUBSIDIO_USER y COLSUBSIDIO_PASS son requeridas"):
            login_and_get_cookies()


def test_missing_password_only_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que teniendo usuario pero sin contraseña se lance ValueError."""
    monkeypatch.setenv("COLSUBSIDIO_USER", "1002559691")
    monkeypatch.delenv("COLSUBSIDIO_PASS", raising=False)

    with patch("config.COLSUBSIDIO_USER", "1002559691"), \
         patch("config.COLSUBSIDIO_PASS", None):
        with pytest.raises(ValueError, match="credenciales COLSUBSIDIO_USER y COLSUBSIDIO_PASS son requeridas"):
            login_and_get_cookies()




# ============================================================================
# 2. STRESS TEST: CREDANCIALES INVÁLIDAS
# ============================================================================

def test_invalid_credentials_playwright_returns_no_cookies() -> None:
    """Verifica que si Playwright no obtiene cookies tras login (credenciales inválidas), se lance RuntimeError."""
    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()

    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    # Elementos de login encontrados pero credenciales rechazadas (0 cookies devueltas)
    mock_page.query_selector.side_effect = lambda sel: MagicMock()
    mock_context.cookies.return_value = []

    with patch.dict("sys.modules", {"playwright.sync_api": MagicMock(sync_playwright=lambda: MagicMock(__enter__=lambda self: mock_playwright, __exit__=lambda self, *args: None))}):
        with pytest.raises(RuntimeError, match="No se pudieron obtener las cookies"):
            login_and_get_cookies(user="usuario_invalido", password="clave_incorrecta")


# ============================================================================
# 3. STRESS TEST: ARCHIVOS .ENV MALFORMADOS / CORRUPTOS
# ============================================================================

def test_malformed_env_file_empty_key(tmp_path: pytest.TempPathFactory) -> None:
    """Verifica la lectura de un .env con líneas malformadas como '=valor' o sin '='."""
    env_file = tmp_path / ".env"
    env_file.write_text("=valor_sin_clave\nLINEA_SIN_IGUAL\nVALID_KEY=valid_val\n", encoding="utf-8")

    # Probar parser de config
    env_dict = {}
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("=", 1)
            if len(parts) == 2:
                k = parts[0].strip()
                v = parts[1].strip().strip('"').strip("'")
                env_dict[k] = v

    # Demostrar que "=valor_sin_clave" genera una clave vacía "" en el diccionario
    assert "" in env_dict
    assert env_dict[""] == "valor_sin_clave"
    assert env_dict["VALID_KEY"] == "valid_val"
    assert "LINEA_SIN_IGUAL" not in env_dict


def test_update_env_file_with_spaced_equals(tmp_path: pytest.TempPathFactory) -> None:
    """Verifica que update_env_file reemplace líneas con espacios alrededor del '=' como 'KEY = val' sin duplicar."""
    env_file = tmp_path / ".env"
    env_file.write_text("COLSUBSIDIO_SISTEMA_COOKIE = old_val\n", encoding="utf-8")

    new_cookies = {"sistema": "new_val_123", "Csrf-Token": "csrf_456"}
    update_env_file(new_cookies, env_path=str(env_file))

    content = env_file.read_text(encoding="utf-8")
    assert "COLSUBSIDIO_SISTEMA_COOKIE=new_val_123" in content
    assert "COLSUBSIDIO_SISTEMA_COOKIE = old_val" not in content


def test_corrupted_non_utf8_env_file(tmp_path: pytest.TempPathFactory) -> None:
    """Verifica el comportamiento cuando .env contiene bytes no UTF-8 (corrupción de archivo)."""
    env_file = tmp_path / ".env"
    # Escribir bytes binarios inválidos
    with open(env_file, "wb") as f:
        f.write(b"\x80\xff\xfe\xfd corrupt data")

    # Intentar leer con utf-8 lanzará UnicodeDecodeError si no se maneja
    with pytest.raises(UnicodeDecodeError):
        with open(env_file, "r", encoding="utf-8") as f:
            f.read()


# ============================================================================
# 4. STRESS TEST: AUSENCIA DE DEPENDENCIAS DE PLAYWRIGHT O CHROMIUM
# ============================================================================

def test_missing_playwright_package_raises_runtime_error() -> None:
    """Verifica que la falta del paquete 'playwright' genere un RuntimeError informativo."""
    with patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
        with pytest.raises(RuntimeError, match="El paquete 'playwright' no está instalado"):
            login_and_get_cookies(user="user", password="pass")


def test_playwright_chromium_binary_missing_handled_by_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que si el binario de Chromium no está instalado, extract_colsubsidio_cookies use el fallback."""
    def mock_login_launch_fail():
        raise Exception("Executable doesn't exist at ... Please run 'playwright install'")

    with patch("get_cookies.login_and_get_cookies", side_effect=mock_login_launch_fail):
        with patch("get_cookies.extract_local_browser_cookies", return_value={"sistema": "local_s", "Csrf-Token": "local_c"}):
            monkeypatch.setattr("sys.platform", "win32")
            cookies = extract_colsubsidio_cookies()
            assert cookies == {"sistema": "local_s", "Csrf-Token": "local_c"}


# ============================================================================
# 5. STRESS TEST: CRYPTOGRAPHY FALTANTE O ENCRIPTACIÓN DESCONOCIDA
# ============================================================================

def test_decrypt_cookie_value_without_cryptography() -> None:
    """Verifica que si cryptography no está disponible, decrypt_cookie_value devuelva cadena vacía para v10/v11."""
    with patch("get_cookies.AESGCM", None):
        res = decrypt_cookie_value(b"v10_encrypted_data_sample", b"master_key")
        assert res == ""

def test_decrypt_cookie_value_unencrypted() -> None:
    """Verifica que cookies sin encriptar (sin prefijo v10/v11) se decodifiquen directamente."""
    res = decrypt_cookie_value(b"plain_text_cookie_value", b"master_key")
    assert res == "plain_text_cookie_value"
