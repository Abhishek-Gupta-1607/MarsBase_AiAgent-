"""Tests for the Alarm Router component."""

import pytest
from router import AlarmRouter, classify_alarm


def test_power_alarm_classification():
    """Verify battery and solar alarms are routed to power category."""
    alarm_battery = {"id": "a1", "system": "power", "title": "Battery Overheating", "description": "Cell bank hot"}
    alarm_solar = {"id": "a2", "system": "unknown", "title": "Solar Array Drop", "description": "Voltage dip"}

    assert classify_alarm(alarm_battery) == "power"
    assert classify_alarm(alarm_solar) == "power"


def test_life_support_alarm_classification():
    """Verify oxygen and ventilation alarms are routed to life_support category."""
    alarm_o2 = {"id": "a3", "system": "life_support", "title": "Oxygen Pressure Low", "description": "Pressure drop"}
    alarm_scrubber = {"id": "a4", "system": "unknown", "title": "Air Scrubber Clogged", "description": "Filter blocked"}

    assert classify_alarm(alarm_o2) == "life_support"
    assert classify_alarm(alarm_scrubber) == "life_support"


def test_unknown_alarm_not_discarded():
    """Verify unknown alarms are categorized into general queue and never silently dropped."""
    alarm_weird = {"id": "a99", "system": "telemetry", "title": "Mysterious Static", "description": "Radio noise"}
    assert classify_alarm(alarm_weird) == "general"

    router = AlarmRouter()
    alarms = [
        {"id": "a1", "system": "power", "title": "Battery", "description": "hot"},
        {"id": "a2", "system": "life_support", "title": "Oxygen", "description": "leak"},
        {"id": "a3", "system": "unknown", "title": "Weird noise", "description": "echo"},
    ]
    routed = router.route_alarms(alarms)

    assert len(routed["power"]) == 1
    assert len(routed["life_support"]) == 1
    assert len(routed["general"]) == 1
    assert routed["routed_count"] == 3
    assert routed["all_count"] == 3
