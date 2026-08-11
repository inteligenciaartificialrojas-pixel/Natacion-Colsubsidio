"""Pruebas unitarias para el módulo get_cookies (autenticación y sincronización de cookies)."""
from __future__ import annotations

import os
import sys
import tempfile
from unittest.mock import patch, MagicMock
import pytest

from get_cookies import (
    login_and_get_cookies,
    extract_colsubsidio_cookies,
    update_env_file,
)


def test_login_and_get_cookies_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que se lance ValueError si no se proporcionan credenciales ni existen en el entorno."""
    monkeypatch.delenv("COLSUBSIDIO_USER", raising=False)
    monkeypatch.delenv("COLSUBSIDIO_PASS", raising=False)
    monkeypatch.delenv("COLSUBSIDIO_DOCUMENT_NUMBER", raising=False)

    with patch("config.COLSUBSIDIO_USER", None), patch("config.COLSUBSIDIO_PASS", None), patch("config.COLSUBSIDIO_DOCUMENT_NUMBER", None):
        with pytest.raises(ValueError, match="credenciales COLSUBSIDIO_USER y COLSUBSIDIO_PASS son requeridas"):
            login_and_get_cookies(user=None, password=None)


@patch("get_cookies.update_env_file")
def test_login_and_get_cookies_success(mock_update_env: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica la autenticación exitosa mediante Playwright simulando las interacciones del navegador."""
    mock_update_env.return_value = True

    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()

    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    # Simular elementos presentes en el DOM de inicio de sesión
    mock_page.query_selector.side_effect = lambda sel: MagicMock() if sel in [
        'select[name="tipo_documento"]',
        'input[name="documento"]',
        'input[name="clave"]',
        'button[type="submit"]'
    ] else None

    # Simular cookies retornadas por el navegador
    mock_context.cookies.return_value = [
        {"name": "sistema", "value": "mock_sistema_val_123", "domain": "diversioncolsubsidio.com"},
        {"name": "Csrf-Token", "value": "mock_csrf_val_456", "domain": "diversioncolsubsidio.com"}
    ]

    with patch.dict("sys.modules", {"playwright.sync_api": MagicMock(sync_playwright=lambda: MagicMock(__enter__=lambda self: mock_playwright, __exit__=lambda self, *args: None))}):
        cookies = login_and_get_cookies(user="1002559691", password="secret_password", headless=True)

    assert cookies == {"sistema": "mock_sistema_val_123", "Csrf-Token": "mock_csrf_val_456"}
    assert os.environ.get("COLSUBSIDIO_SISTEMA_COOKIE") == "mock_sistema_val_123"
    assert os.environ.get("COLSUBSIDIO_CSRF_TOKEN") == "mock_csrf_val_456"
    mock_update_env.assert_called_once_with({"sistema": "mock_sistema_val_123", "Csrf-Token": "mock_csrf_val_456"})


def test_login_and_get_cookies_invalid_credentials() -> None:
    """Verifica que se lance RuntimeError cuando el inicio de sesión falla o no produce cookies válidas."""
    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()

    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    mock_page.query_selector.return_value = None
    # No se obtienen cookies tras enviar credenciales inválidas
    mock_context.cookies.return_value = []

    with patch.dict("sys.modules", {"playwright.sync_api": MagicMock(sync_playwright=lambda: MagicMock(__enter__=lambda self: mock_playwright, __exit__=lambda self, *args: None))}):
        with pytest.raises(RuntimeError, match="No se pudieron obtener las cookies"):
            login_and_get_cookies(user="invalid_user", password="wrong_password", headless=True)


def test_update_env_file(tmp_path: pytest.TempPathFactory) -> None:
    """Verifica la creación y actualización correcta de las cookies en el archivo .env."""
    test_env = tmp_path / ".env"
    test_env.write_text("TELEGRAM_TOKEN=12345\nCOLSUBSIDIO_SISTEMA_COOKIE=old_sistema\n", encoding="utf-8")

    new_cookies = {"sistema": "new_sistema_abc", "Csrf-Token": "new_csrf_xyz"}
    success = update_env_file(new_cookies, env_path=str(test_env))

    assert success is True
    content = test_env.read_text(encoding="utf-8")
    assert "COLSUBSIDIO_SISTEMA_COOKIE=new_sistema_abc" in content
    assert "COLSUBSIDIO_CSRF_TOKEN=new_csrf_xyz" in content
    assert "TELEGRAM_TOKEN=12345" in content


@patch("get_cookies.login_and_get_cookies")
def test_extract_colsubsidio_cookies_uses_playwright_primary(mock_login: MagicMock) -> None:
    """Verifica que extract_colsubsidio_cookies use login_and_get_cookies como mecanismo primario."""
    mock_login.return_value = {"sistema": "playwright_s", "Csrf-Token": "playwright_c"}

    cookies = extract_colsubsidio_cookies()

    assert cookies == {"sistema": "playwright_s", "Csrf-Token": "playwright_c"}
    mock_login.assert_called_once()


@patch("get_cookies.extract_local_browser_cookies")
@patch("get_cookies.login_and_get_cookies")
def test_extract_colsubsidio_cookies_fallback_on_windows(mock_login: MagicMock, mock_local: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que extract_colsubsidio_cookies use el fallback local si falla Playwright en Windows."""
    mock_login.side_effect = RuntimeError("Playwright login failed")
    mock_local.return_value = {"sistema": "fallback_s", "Csrf-Token": "fallback_c"}
    monkeypatch.setattr("sys.platform", "win32")

    cookies = extract_colsubsidio_cookies()

    assert cookies == {"sistema": "fallback_s", "Csrf-Token": "fallback_c"}
    mock_login.assert_called_once()
    mock_local.assert_called_once()


@patch("get_cookies.extract_local_browser_cookies")
@patch("get_cookies.login_and_get_cookies")
def test_extract_colsubsidio_cookies_non_windows_fallback_returns_empty_dict(mock_login: MagicMock, mock_local: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que extract_colsubsidio_cookies retorne dict vacío si Playwright falla en plataformas no-Windows."""
    mock_login.side_effect = RuntimeError("Playwright login failed")
    monkeypatch.setattr("sys.platform", "linux")

    cookies = extract_colsubsidio_cookies()

    assert cookies == {}
    mock_login.assert_called_once()
    mock_local.assert_not_called()


def test_decrypt_cookie_value_when_aesgcm_is_none() -> None:
    """Verifica que decrypt_cookie_value devuelva una cadena vacía si AESGCM es None."""
    from get_cookies import decrypt_cookie_value
    with patch("get_cookies.AESGCM", None):
        val = decrypt_cookie_value(b"v10_encrypted_value", b"master_key")
        assert val == ""

