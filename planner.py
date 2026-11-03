"""Planner and Plan Validator implementing the pattern from Part 8 of the notebook.

Prepares structured action plans, validates them using deterministic Python,
and interfaces safely with the simulator.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from rules import PythonRuleChecker
from config import VALID_REPAIR_TARGETS


class MissionPlanner:
    """Generates and validates mission plans before execution."""

    @staticmethod
    def create_deterministic_survival_plan(
        sol: int,
        resource_eval: Dict[str, Any],
        power_report: Dict[str, Any],
        life_report: Dict[str, Any],
        available_kits: int,
    ) -> List[Dict[str, Any]]:
        """Create a safety-first baseline plan based on deterministic rules and specialist reports."""
        if available_kits <= 0:
            return []

        plan: List[Dict[str, Any]] = []

        # Sol 3: Catastrophic dual failure - Human survival first!
        if sol == 3:
            # Oxygen failure is lethal, must repair oxygen_generator
            plan.append({
                "action": "repair",
                "target": "oxygen_generator",
                "kits": 1,
                "priority": "HIGH_SURVIVAL",
            })
            return plan

        # General priority assessment
        recommended_priority = resource_eval.get("recommended_priority")
        if recommended_priority == "oxygen_generator" and available_kits >= 1:
            plan.append({
                "action": "repair",
                "target": "oxygen_generator",
                "kits": 1,
                "priority": "LIFE_SUPPORT",
            })
        elif recommended_priority == "battery_bank" and available_kits >= 1:
            plan.append({
                "action": "repair",
                "target": "battery_bank",
                "kits": 1,
                "priority": "POWER_GRID",
            })
        else:
            # Check specialist recommendations
            life_target = life_report.get("recommended_target")
            power_target = power_report.get("recommended_target")

            if life_target in VALID_REPAIR_TARGETS and available_kits >= 1:
                plan.append({
                    "action": "repair",
                    "target": life_target,
                    "kits": 1,
                    "priority": "LIFE_SUPPORT",
                })
            elif power_target in VALID_REPAIR_TARGETS and available_kits >= 1:
                plan.append({
                    "action": "repair",
                    "target": power_target,
                    "kits": 1,
                    "priority": "POWER_GRID",
                })

        return plan

    @classmethod
    def validate_plan(cls, plan_data: Any, available_kits: int) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
        """Validate proposed plan using strict deterministic Python rules."""
        errors: List[str] = []
        cleaned_actions: List[Dict[str, Any]] = []

        # Check if plan_data is a JSON string or list/dict
        if isinstance(plan_data, str):
            try:
                # Strip code fences if present
                clean = plan_data.strip()
                if clean.startswith("```"):
                    lines = clean.split("\n")
                    clean = "\n".join(lines[1:-1])
                parsed = json.loads(clean)
                if isinstance(parsed, dict) and "actions" in parsed:
                    plan_data = parsed["actions"]
                elif isinstance(parsed, list):
                    plan_data = parsed
                else:
                    return False, ["Plan must resolve to a list of actions or contain an 'actions' list."], []
            except Exception as e:
                return False, [f"Failed to parse plan JSON: {e}"], []

        if not isinstance(plan_data, list):
            return False, ["Plan must be a list of action items."], []

        valid, rule_errors = PythonRuleChecker.validate_actions_list(plan_data, available_kits)
        if not valid:
            errors.extend(rule_errors)
        else:
            for act in plan_data:
                cleaned_actions.append({
                    "action": act["action"],
                    "target": act["target"],
                    "kits": int(act["kits"]),
                })

        return (len(errors) == 0, errors, cleaned_actions)
