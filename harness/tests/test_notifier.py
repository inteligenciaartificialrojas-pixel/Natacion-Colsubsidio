"""Pruebas unitarias para el módulo notifier (Telegram)."""
from __future__ import annotations
from unittest.mock import patch, MagicMock
import pytest
import requests
from notifier import TelegramNotifier

def test_notifier_init() -> None:
    """Verifica que el notificador se inicialice correctamente con credenciales."""
    notifier = TelegramNotifier(token="fake_token", chat_id="fake_chat_id")
    assert notifier.token == "fake_token"
    assert notifier.chat_id == "fake_chat_id"

@patch("notifier.TELEGRAM_TOKEN", None)
@patch("notifier.TELEGRAM_CHAT_ID", None)
def test_send_message_missing_credentials() -> None:
    """Verifica que si no hay token ni chat_id, el mensaje no se envíe y retorne False."""
    notifier = TelegramNotifier(token=None, chat_id=None)
    assert not notifier.send_message("Hello")

@patch("requests.post")
def test_send_message_success(mock_post: MagicMock) -> None:
    """Verifica el envío exitoso de un mensaje de Telegram."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    notifier = TelegramNotifier(token="token", chat_id="chat_id")
    assert notifier.send_message("Hello")
    mock_post.assert_called_once_with(
        "https://api.telegram.org/bottoken/sendMessage",
        json={"chat_id": "chat_id", "text": "Hello", "parse_mode": "Markdown"},
        timeout=10
    )

@patch("requests.post")
def test_send_message_http_error(mock_post: MagicMock) -> None:
    """Verifica que un error HTTP del API de Telegram retorne False."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_post.return_value = mock_response

    notifier = TelegramNotifier(token="token", chat_id="chat_id")
    assert not notifier.send_message("Hello")

@patch("requests.post")
def test_send_message_network_error(mock_post: MagicMock) -> None:
    """Verifica que un error de red / excepción de requests retorne False sin colapsar."""
    mock_post.side_effect = requests.RequestException("Connection timed out")

    notifier = TelegramNotifier(token="token", chat_id="chat_id")
    assert not notifier.send_message("Hello")

@patch("requests.post")
def test_notify_venue_slots_deduplication(mock_post: MagicMock) -> None:
    """Verifica que se filtren alertas de sedes idénticas dentro de la ventana de caché."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    notifier = TelegramNotifier(token="token", chat_id="chat_id", cache_duration_seconds=10)

    slots_1 = [
        {"fecha": "2026-06-10", "hora": "18:00", "cupos": 5},
        {"fecha": "2026-06-10", "hora": "19:00", "cupos": 2}
    ]

    # La primera alerta debe enviarse
    assert notifier.notify_venue_slots("El Cubo", slots_1) is True
    assert mock_post.call_count == 1

    # La segunda alerta idéntica debe suprimirse
    assert notifier.notify_venue_slots("El Cubo", slots_1) is False
    assert mock_post.call_count == 1

    # Una alerta con cambio en los cupos debe pasar
    slots_2 = [
        {"fecha": "2026-06-10", "hora": "18:00", "cupos": 5},
        {"fecha": "2026-06-10", "hora": "19:00", "cupos": 3}
    ]
    assert notifier.notify_venue_slots("El Cubo", slots_2) is True
    assert mock_post.call_count == 2

@patch("requests.post")
@patch("time.time")
def test_notify_venue_slots_expiration(mock_time: MagicMock, mock_post: MagicMock) -> None:
    """Verifica que expire la caché del compilado y vuelva a notificar después del tiempo definido."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    mock_time.return_value = 1000.0

    notifier = TelegramNotifier(token="token", chat_id="chat_id", cache_duration_seconds=10)

    slots = [{"fecha": "2026-06-10", "hora": "18:00", "cupos": 5}]

    # Alerta inicial
    assert notifier.notify_venue_slots("El Cubo", slots) is True
    assert mock_post.call_count == 1

    # Avance de tiempo menor a la duración de la caché
    mock_time.return_value = 1005.0
    assert notifier.notify_venue_slots("El Cubo", slots) is False
    assert mock_post.call_count == 1

    # Avance de tiempo mayor a la duración de la caché (11 segundos transcurridos)
    mock_time.return_value = 1011.0
    assert notifier.notify_venue_slots("El Cubo", slots) is True
    assert mock_post.call_count == 2
