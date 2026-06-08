"""Pruebas unitarias para el módulo main (Orquestador y Filtros)."""
from __future__ import annotations
from unittest.mock import patch, MagicMock
import pytest
import time
from scraper import SessionExpiredException
from main import is_within_preferred_schedule, check_venues

def test_is_within_preferred_schedule_weekdays() -> None:
    """Verifica que el filtro de horarios entre semana (L-V) funcione correctamente."""
    # Lunes regular (2026-06-01) - No festivo
    monday = "2026-06-01"
    assert is_within_preferred_schedule(monday, "18:00") is True
    assert is_within_preferred_schedule(monday, "19:30") is True
    assert is_within_preferred_schedule(monday, "20:00") is True
    assert is_within_preferred_schedule(monday, "17:59") is False
    assert is_within_preferred_schedule(monday, "21:00") is False

def test_is_within_preferred_schedule_holidays() -> None:
    """Verifica que los festivos en Colombia permitan cualquier horario."""
    # Lunes festivo (2026-06-08) - Corpus Christi
    holiday_monday = "2026-06-08"
    assert is_within_preferred_schedule(holiday_monday, "06:00") is True
    assert is_within_preferred_schedule(holiday_monday, "12:00") is True
    assert is_within_preferred_schedule(holiday_monday, "21:00") is True

def test_is_within_preferred_schedule_weekends() -> None:
    """Verifica que los fines de semana (S-D) permitan cualquier horario."""
    # Sábado (2026-06-13)
    saturday = "2026-06-13"
    assert is_within_preferred_schedule(saturday, "06:00") is True
    assert is_within_preferred_schedule(saturday, "12:00") is True
    assert is_within_preferred_schedule(saturday, "21:00") is True

@patch("scraper.ColsubsidioScraper")
@patch("notifier.TelegramNotifier")
def test_check_venues_integration(mock_notifier_cls: MagicMock, mock_scraper_cls: MagicMock) -> None:
    """Verifica que check_venues filtre y notifique correctamente los cupos válidos."""
    scraper = mock_scraper_cls()
    notifier = mock_notifier_cls()

    # Configurar mock del scraper
    # Retorna calendario de fechas
    scraper.fetch_available_dates.return_value = ["2026-06-01", "2026-06-13"]
    
    # Retorna slots para cada fecha
    def mock_fetch_slots(service_id: int, date_str: str) -> list[dict]:
        if date_str == "2026-06-01":
            # Lunes: un slot válido (18:30) y uno inválido (15:00)
            return [
                {"fecha": "2026-06-01", "hora": "18:30", "cupos": 2},
                {"fecha": "2026-06-01", "hora": "15:00", "cupos": 1}
            ]
        elif date_str == "2026-06-13":
            # Sábado: cualquier slot es válido
            return [
                {"fecha": "2026-06-13", "hora": "08:00", "cupos": 5}
            ]
        return []

    scraper.fetch_slots_for_date.side_effect = mock_fetch_slots

    check_venues(scraper, notifier)

    # Debería haber notificado para las 3 sedes el consolidado (3 llamadas)
    assert notifier.notify_venue_slots.call_count == 3
    expected_slots = [
        {"fecha": "2026-06-01", "hora": "18:30", "cupos": 2},
        {"fecha": "2026-06-13", "hora": "08:00", "cupos": 5}
    ]
    notifier.notify_venue_slots.assert_any_call("EL CUBO", expected_slots)
    notifier.notify_venue_slots.assert_any_call("PLAZA DE LAS AMERICAS", expected_slots)
    notifier.notify_venue_slots.assert_any_call("CLUB LA COLINA", expected_slots)

@patch("scraper.ColsubsidioScraper")
@patch("notifier.TelegramNotifier")
def test_check_venues_raises_expired(mock_notifier_cls: MagicMock, mock_scraper_cls: MagicMock) -> None:
    """Verifica que check_venues propague la excepción de sesión expirada."""
    scraper = mock_scraper_cls()
    notifier = mock_notifier_cls()

    scraper.fetch_available_dates.side_effect = SessionExpiredException("Expired")

    with pytest.raises(SessionExpiredException):
        check_venues(scraper, notifier)
