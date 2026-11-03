"""Shared Mission Blackboard for Mars Base.

Implements shared state across workflow nodes (using ctx.set_state and ctx.get_state)
and persists mission memory across all five sols into mission_state.json.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from agent_framework import WorkflowContext
from config import MISSION_STATE_PATH


class MissionBlackboard:
    """Persistent mission memory across all 5 sols."""

    def __init__(self, state_path: Optional[Path] = None):
        self.state_path = state_path or MISSION_STATE_PATH
        self.data: Dict[str, Any] = {
            "current_sol": 1,
            "previous_alarms": [],
            "current_alarms": [],
            "crew_messages": [],
            "power_report": "",
            "life_report": "",
            "system_failures": [],
            "crew_positions": [],
            "nearby_failures_log": [],
            "suspicious_activities": [],
            "evidence_ids": [],
            "suspect_scores": {},
            "previous_decisions": [],
            "remaining_repair_kits": 5,
            "mission_history": [],
        }

    def update_for_sol(
        self,
        sol: int,
        alarms: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        repair_kits: int,
        crew: List[Dict[str, Any]],
        evidence_available: List[str],
    ) -> None:
        """Update blackboard state at the beginning of each sol."""
        # Archive current alarms into previous_alarms
        if self.data["current_alarms"]:
            self.data["previous_alarms"].extend(self.data["current_alarms"])

        self.data["current_sol"] = sol
        self.data["current_alarms"] = alarms
        self.data["crew_messages"] = messages
        self.data["remaining_repair_kits"] = repair_kits
        self.data["crew_positions"] = crew
        self.data["power_report"] = ""
        self.data["life_report"] = ""

        # Record nearby failures
        for a in alarms:
            self.data["nearby_failures_log"].append({
                "sol": sol,
                "alarm_id": a.get("id"),
                "nearby": a.get("nearby_crew", []),
                "location": a.get("location", ""),
            })

        for ev in evidence_available:
            if ev not in self.data["evidence_ids"]:
                self.data["evidence_ids"].append(ev)

        self.save()

    def record_decision(self, decision: Dict[str, Any], sim_result: Dict[str, Any]) -> None:
        """Record completed decision and simulator outcome."""
        self.data["previous_decisions"].append(decision)
        self.data["mission_history"].append({
            "sol": decision.get("sol"),
            "decision": decision,
            "result": sim_result,
        })
        self.save()

    def save(self) -> None:
        """Persist blackboard to JSON file."""
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"[Warning] Failed to persist blackboard: {e}")

    def load(self) -> None:
        """Load blackboard state from JSON file if present."""
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f"[Warning] Failed to load blackboard from {self.state_path}: {e}")

    # Helper methods for WorkflowContext synchronization
    def populate_context(self, ctx: WorkflowContext) -> None:
        """Copy blackboard state into WorkflowContext for workflow executors."""
        for key, value in self.data.items():
            ctx.set_state(key, value)

    def sync_from_context(self, ctx: WorkflowContext) -> None:
        """Synchronize updated state from WorkflowContext back into the blackboard."""
        for key in ["power_report", "life_report", "commander_plan", "safety_status"]:
            try:
                val = ctx.get_state(key)
                if val is not None:
                    self.data[key] = val
            except Exception:
                pass
        self.save()
