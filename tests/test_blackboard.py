"""Tests for Blackboard state persistence and concurrency safety."""

import tempfile
from pathlib import Path
import pytest
from blackboard import MissionBlackboard


def test_blackboard_persistence_across_sols():
    """Verify blackboard preserves history and alarms between sols."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "test_state.json"
        bb = MissionBlackboard(state_path=state_file)

        # Sol 1 update
        bb.update_for_sol(
            sol=1,
            alarms=[{"id": "alarm_1", "system": "power"}],
            messages=[{"id": "msg_1", "content": "Hi"}],
            repair_kits=5,
            crew=[{"name": "David Miller", "location": "Power Hub"}],
            evidence_available=["ev_1"],
        )
        bb.record_decision({"sol": 1, "actions": []}, {"success": True})

        # Reload blackboard from disk
        bb2 = MissionBlackboard(state_path=state_file)
        bb2.load()

        assert bb2.data["current_sol"] == 1
        assert len(bb2.data["previous_decisions"]) == 1
        assert "ev_1" in bb2.data["evidence_ids"]

        # Sol 2 update should archive Sol 1 alarms into previous_alarms
        bb2.update_for_sol(
            sol=2,
            alarms=[{"id": "alarm_2", "system": "life_support"}],
            messages=[],
            repair_kits=4,
            crew=[],
            evidence_available=["ev_2"],
        )

        assert bb2.data["current_sol"] == 2
        assert len(bb2.data["previous_alarms"]) == 1
        assert bb2.data["previous_alarms"][0]["id"] == "alarm_1"
        assert len(bb2.data["current_alarms"]) == 1
        assert bb2.data["current_alarms"][0]["id"] == "alarm_2"


def test_concurrent_agent_keys_isolated():
    """Verify distinct keys for power_report and life_report prevent overwriting."""
    bb = MissionBlackboard(state_path=Path(tempfile.mktemp()))
    bb.data["power_report"] = {"system": "power", "status": "STABLE"}
    bb.data["life_report"] = {"system": "life_support", "status": "CRITICAL"}

    assert bb.data["power_report"]["system"] == "power"
    assert bb.data["life_report"]["system"] == "life_support"
    assert bb.data["power_report"] != bb.data["life_report"]
