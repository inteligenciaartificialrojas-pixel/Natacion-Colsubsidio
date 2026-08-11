"""Pruebas adversariales de estrés para get_cookies (concurrencia, parámetros y .env update)."""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock
import pytest

from get_cookies import (
    login_and_get_cookies,
    update_env_file,
)


# ============================================================================
# 1. PRUEBAS DE CONCURRENCIA (CONCURRENCY STRESS TESTS)
# ============================================================================

def test_update_env_file_concurrency(tmp_path: pytest.TempPath) -> None:
    """Verifica el comportamiento de update_env_file ante accesos concurrentes multitítulo.
    
    Demuestra la vulnerabilidad de condición de carrera y truncamiento no atómico.
    """
    env_file = tmp_path / ".env"
    env_file.write_text(
        "COLSUBSIDIO_SISTEMA_COOKIE=init_sistema\nCOLSUBSIDIO_CSRF_TOKEN=init_csrf\nOTHER_KEY=keep_me\n",
        encoding="utf-8"
    )

    errors = []

    def worker(idx: int) -> None:
        try:
            cookies = {
                "sistema": f"sistema_val_{idx}",
                "Csrf-Token": f"csrf_val_{idx}"
            }
            res = update_env_file(cookies, env_path=str(env_file))
            if not res:
                errors.append(f"Worker {idx} returned False")
        except Exception as e:
            errors.append(f"Worker {idx} exception: {e}")

    threads = []
    for i in range(10):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Verificar integridad del archivo .env post-ejecución concurrente
    content = env_file.read_text(encoding="utf-8")
    assert "OTHER_KEY=keep_me" in content, "Fallo de concurrencia: OTHER_KEY fue corrompido o eliminado del .env"
    assert "COLSUBSIDIO_SISTEMA_COOKIE=" in content
    assert "COLSUBSIDIO_CSRF_TOKEN=" in content


def test_login_and_get_cookies_concurrency_race_condition() -> None:
    """Verifica el comportamiento de login_and_get_cookies ante llamados concurrentes."""
    mock_update = MagicMock(return_value=True)

    results = {}

    def run_login(thread_id: int):
        user_id = f"user_{thread_id}"
        pass_word = f"pass_{thread_id}"
        
        mock_cookies = [
            {"name": "sistema", "value": f"sistema_{thread_id}"},
            {"name": "Csrf-Token", "value": f"csrf_{thread_id}"}
        ]

        def fake_playwright_ctx():
            mock_p = MagicMock()
            mock_browser = MagicMock()
            mock_context = MagicMock()
            mock_page = MagicMock()
            mock_p.chromium.launch.return_value = mock_browser
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page
            mock_page.query_selector.return_value = MagicMock()
            mock_context.cookies.return_value = mock_cookies
            return MagicMock(__enter__=lambda s: mock_p, __exit__=lambda s, *a: None)

        with patch("get_cookies.update_env_file", mock_update):
            with patch.dict("sys.modules", {"playwright.sync_api": MagicMock(sync_playwright=fake_playwright_ctx)}):
                try:
                    res = login_and_get_cookies(user=user_id, password=pass_word, headless=True)
                    results[thread_id] = res
                except Exception as ex:
                    results[thread_id] = ex

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(run_login, i) for i in range(3)]
        for f in futures:
            f.result()

    for i in range(3):
        assert i in results
        assert isinstance(results[i], dict)
        assert results[i]["sistema"] == f"sistema_{i}"


# ============================================================================
# 2. PRUEBAS DE PARÁMETROS PERSONALIZADOS (CUSTOM PARAMETERS TESTS)
# ============================================================================

def test_login_and_get_cookies_empty_string_credential_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que 'user=""' o 'password=""' no caiga en fallback a variables de entorno, lanzando ValueError."""
    monkeypatch.setenv("COLSUBSIDIO_USER", "env_user_123")
    monkeypatch.setenv("COLSUBSIDIO_PASS", "env_pass_456")

    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page
    mock_page.query_selector.return_value = MagicMock()
    mock_context.cookies.return_value = [
        {"name": "sistema", "value": "s_val"},
        {"name": "Csrf-Token", "value": "c_val"}
    ]

    with patch("get_cookies.update_env_file", return_value=True):
        with patch.dict("sys.modules", {"playwright.sync_api": MagicMock(sync_playwright=lambda: MagicMock(__enter__=lambda s: mock_playwright, __exit__=lambda s, *a: None))}):
            with pytest.raises(ValueError, match="credenciales"):
                login_and_get_cookies(user="", password="valid_password", headless=True)


def test_login_and_get_cookies_numeric_user_type_handling() -> None:
    """Verifica que cuando user o password se pasan como int se casteen a string sin lanzar TypeError."""
    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page
    mock_page.query_selector.return_value = MagicMock()
    mock_context.cookies.return_value = [
        {"name": "sistema", "value": "s_val"},
        {"name": "Csrf-Token", "value": "c_val"}
    ]

    def strict_fill(selector: str, value: str):
        if not isinstance(value, str):
            raise TypeError(f"value: expected string, got {type(value).__name__}")

    mock_page.fill.side_effect = strict_fill

    with patch("get_cookies.update_env_file", return_value=True):
        with patch.dict("sys.modules", {"playwright.sync_api": MagicMock(sync_playwright=lambda: MagicMock(__enter__=lambda s: mock_playwright, __exit__=lambda s, *a: None))}):
            res = login_and_get_cookies(user=1002559691, password=123456, headless=True) # type: ignore
            assert res == {"sistema": "s_val", "Csrf-Token": "c_val"}


def test_login_and_get_cookies_headless_string_coercion() -> None:
    """Verifica que el argumento 'headless' se cohesione a booleano cuando recibe una cadena 'False'."""
    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_playwright.chromium.launch.return_value = mock_browser

    with patch("get_cookies.update_env_file", return_value=True):
        with patch.dict("sys.modules", {"playwright.sync_api": MagicMock(sync_playwright=lambda: MagicMock(__enter__=lambda s: mock_playwright, __exit__=lambda s, *a: None))}):
            try:
                login_and_get_cookies(user="u", password="p", headless="False") # type: ignore
            except Exception:
                pass

    launch_kwargs = mock_playwright.chromium.launch.call_args[1]
    assert launch_kwargs.get("headless") is False


# ============================================================================
# 3. PRUEBAS DE LÓGICA DE ACTUALIZACIÓN DE .ENV (UPDATE_ENV_FILE LOGIC TESTS)
# ============================================================================

def test_update_env_file_partial_dict_destroys_existing_token(tmp_path: pytest.TempPath) -> None:
    """Verifica que update_env_file no elimine un token existente si solo se pasa una de las cookies."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "COLSUBSIDIO_SISTEMA_COOKIE=old_sistema\nCOLSUBSIDIO_CSRF_TOKEN=valid_csrf_token_999\n",
        encoding="utf-8"
    )

    partial_cookies = {"sistema": "new_sistema_val"}

    success = update_env_file(partial_cookies, env_path=str(env_file))
    assert success is True

    content = env_file.read_text(encoding="utf-8")
    assert "COLSUBSIDIO_SISTEMA_COOKIE=new_sistema_val" in content
    assert "COLSUBSIDIO_CSRF_TOKEN=valid_csrf_token_999" in content, \
        "Remediación confirmada: update_env_file preservó COLSUBSIDIO_CSRF_TOKEN al recibir dict parcial."


def test_update_env_file_spaced_formatting_creates_duplicates(tmp_path: pytest.TempPath) -> None:
    """Verifica que update_env_file no cree llaves duplicadas si el .env usa espacios alrededor de '='."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "COLSUBSIDIO_SISTEMA_COOKIE = old_val\nCOLSUBSIDIO_CSRF_TOKEN = old_csrf\n",
        encoding="utf-8"
    )

    new_cookies = {"sistema": "sistema_fresh", "Csrf-Token": "csrf_fresh"}
    update_env_file(new_cookies, env_path=str(env_file))

    content = env_file.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    assert "COLSUBSIDIO_SISTEMA_COOKIE=sistema_fresh" in lines
    assert "COLSUBSIDIO_CSRF_TOKEN=csrf_fresh" in lines
    assert "COLSUBSIDIO_SISTEMA_COOKIE = old_val" not in lines
    assert len([l for l in lines if "COLSUBSIDIO_SISTEMA_COOKIE" in l]) == 1


def test_update_env_file_newline_injection(tmp_path: pytest.TempPath) -> None:
    """Verifica la seguridad contra inyección de saltos de línea en valores de cookies."""
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_VAR=1\n", encoding="utf-8")

    malicious_cookies = {
        "sistema": "token_val\nMALICIOUS_INJECTED_VAR=hacked",
        "Csrf-Token": "csrf_val"
    }

    update_env_file(malicious_cookies, env_path=str(env_file))

    content = env_file.read_text(encoding="utf-8")
    lines = content.splitlines()
    assert "MALICIOUS_INJECTED_VAR=hacked" not in lines, \
        "Remediación confirmada: Inyección de salto de línea fue prevenida exitosamente."


def test_update_env_file_nonexistent_directory(tmp_path: pytest.TempPath) -> None:
    """Verifica la resistencia ante rutas de archivo en directorios inexistentes."""
    nonexistent_env = tmp_path / "nonexistent_dir" / "nested" / ".env"
    
    success = update_env_file({"sistema": "s", "Csrf-Token": "c"}, env_path=str(nonexistent_env))
    assert success is False
