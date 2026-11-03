"""Tests for deterministic Python Rule Checker."""

import pytest
from rules import PythonRuleChecker


def test_resource_sols_calculation():
    """Verify remaining sols calculation is accurate."""
    # 100 / 20 = 5.0 sols
    assert PythonRuleChecker.calculate_resource_sols(100.0, 20.0) == 5.0
    # 75.5 / 15.0 = 5.03 sols
    assert PythonRuleChecker.calculate_resource_sols(75.5, 15.0) == 5.03


def test_zero_and_negative_consumption_handling():
    """Verify safe handling of zero or negative consumption rates."""
    assert PythonRuleChecker.calculate_resource_sols(100.0, 0.0) == 999.0
    assert PythonRuleChecker.calculate_resource_sols(100.0, -5.0) == 999.0
    assert PythonRuleChecker.calculate_resource_sols(0.0, 15.0) == 0.0
    assert PythonRuleChecker.calculate_resource_sols(-10.0, 15.0) == 0.0
    assert PythonRuleChecker.calculate_resource_sols(None, 15.0) == 0.0


def test_evaluate_resources():
    """Verify full deterministic resource evaluation and priority flag."""
    state = {
        "oxygen": 80.0,
        "oxygen_consumption_rate": 20.0,
        "power": 90.0,
        "power_consumption_rate": 10.0,
        "repair_kits": 4,
    }
    result = PythonRuleChecker.evaluate_resources(state)
    assert result["oxygen_sols_remaining"] == 4.0
    assert result["power_sols_remaining"] == 9.0
    assert result["repair_kits_available"] == 4


def test_invalid_action_rejected():
    """Verify invalid action verbs, targets, or negative kits are rejected."""
    # Invalid action verb
    valid, err = PythonRuleChecker.validate_action({"action": "sabotage", "target": "battery_bank", "kits": 1}, 3)
    assert not valid
    assert "Invalid action" in err

    # Invalid target
    valid, err = PythonRuleChecker.validate_action({"action": "repair", "target": "coffee_maker", "kits": 1}, 3)
    assert not valid
    assert "Invalid repair target" in err

    # Invalid kits
    valid, err = PythonRuleChecker.validate_action({"action": "repair", "target": "battery_bank", "kits": 0}, 3)
    assert not valid
    assert "Invalid kit amount" in err


def test_insufficient_repair_kits_detected():
    """Verify action requesting more kits than inventory is rejected."""
    actions = [
        {"action": "repair", "target": "oxygen_generator", "kits": 2},
        {"action": "repair", "target": "battery_bank", "kits": 2},
    ]
    # Available = 3, requested = 4
    valid, errors = PythonRuleChecker.validate_actions_list(actions, available_kits=3)
    assert not valid
    assert any("exceeds available kits" in e for e in errors)
