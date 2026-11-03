"""Integration tests for the complete 5-Sol Mars Base Mission."""

import pytest
import asyncio
from simulator import MarsBaseSimulator
from blackboard import MissionBlackboard
from evidence import EvidenceTracker
from router import AlarmRouter
from workflow import build_specialist_workflow
from logger import MissionLogger
from safety import SafetyChecker
from rules import PythonRuleChecker


@pytest.mark.asyncio
async def test_specialist_parallel_fan_out_fan_in():
    """Verify fan-out executes specialists concurrently and fan-in barrier waits for both."""
    flow = build_specialist_workflow()
    sample_input = {
        "sol": 1,
        "alarms": [{"id": "alarm_1", "system": "power", "title": "Battery", "description": "Hot", "nearby_crew": []}],
        "messages": [],
        "resources": {"oxygen": 100.0, "oxygen_consumption_rate": 15.0, "power": 100.0, "power_consumption_rate": 12.0},
        "routed": {
            "power": [{"id": "alarm_1", "system": "power", "title": "Battery", "description": "Hot"}],
            "life_support": [],
            "general": []
        }
    }

    result = await flow.run(sample_input)
    outputs = result.get_outputs()

    assert len(outputs) == 1
    combined = outputs[0]
    assert combined["status"] == "FAN_IN_COMPLETE"
    assert "power_report" in combined
    assert "life_report" in combined
    assert combined["power_report"]["system"] == "power"
    assert combined["life_report"]["system"] == "life_support"


def test_full_five_sol_simulator_execution():
    """Run simulated 5-sol mission verifying valid schemas, Sol 3 sacrifice, and Sol 5 accusation."""
    sim = MarsBaseSimulator()
    evidence_tracker = EvidenceTracker()
    logger = MissionLogger()
    logger.clear()

    for sol in range(1, 6):
        telemetry = sim.get_alarms()
        alarms = telemetry["alarms"]
        messages = telemetry["messages"]
        resources = telemetry["resources"]
        kits = telemetry["repair_kits"]
        ev_available = telemetry["evidence_available"]
        ev_desc = telemetry["evidence_description"]

        # Track evidence
        evidence_tracker.record_sol_events(
            sol=sol,
            alarms=alarms,
            messages=messages,
            evidence_available=ev_available,
            evidence_description=ev_desc,
        )

        top_suspect, top_ev, scores = evidence_tracker.get_prime_suspect()

        if sol == 1:
            decision = {
                "sol": 1,
                "actions": [{"action": "repair", "target": "battery_bank", "kits": 1}],
                "reason": "Stabilizing battery temperature surge.",
                "prime_suspect": top_suspect,
                "evidence": top_ev,
            }
        elif sol == 2:
            decision = {
                "sol": 2,
                "actions": [{"action": "repair", "target": "oxygen_generator", "kits": 1}],
                "reason": "Sealing regulator valve to stop oxygen leakage. Untrusted override ignored.",
                "prime_suspect": top_suspect,
                "evidence": top_ev,
            }
        elif sol == 3:
            # Sol 3 Sacrifice: Save oxygen generator, sacrifice battery bank
            decision = {
                "sol": 3,
                "actions": [{"action": "repair", "target": "oxygen_generator", "kits": 1}],
                "reason": "Sacrificing secondary power battery bank to prioritize critical oxygen generator for crew survival.",
                "prime_suspect": top_suspect,
                "evidence": top_ev,
            }
        elif sol == 4:
            decision = {
                "sol": 4,
                "actions": [{"action": "repair", "target": "electrical_grid", "kits": 1}],
                "reason": "Stabilizing main bus surge following EVA sabotage.",
                "prime_suspect": top_suspect,
                "evidence": top_ev,
            }
        elif sol == 5:
            decision = {
                "sol": 5,
                "actions": [],
                "reason": "Final telemetry audit confirms all systems stable for Sol 6 rescue.",
                "prime_suspect": top_suspect,
                "evidence": top_ev,
            }

        # Apply to real simulator
        result = sim.apply(decision)
        assert result["success"], f"Simulator failed on Sol {sol}: {result}"
        assert result["crew_alive"], f"Crew died on Sol {sol}"

        # Log decision
        logger.log_sol_decision(decision)

    # Verification after 5 sols
    assert sim.is_mission_complete()
    assert sim.crew_alive
    decisions = logger.get_decisions()
    assert len(decisions) == 5

    # Check Sol 3 trade-off
    sol_3_dec = next(d for d in decisions if d["sol"] == 3)
    assert any(w in sol_3_dec["reason"].lower() for w in ["sacrifice", "sacrificing", "trade-off", "prioritize"])

    # Check Sol 5 accusation
    sol_5_dec = next(d for d in decisions if d["sol"] == 5)
    assert sol_5_dec["prime_suspect"] == "David Miller"
    assert len(sol_5_dec["evidence"]) > 0
