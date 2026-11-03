"""Deterministic Python Rule Checker for Mars Base resources and action validation.

Uses plain Python without LLM calls for safety-critical calculations.
"""

from typing import Any, Dict, List, Optional, Tuple
from config import VALID_REPAIR_TARGETS


class PythonRuleChecker:
    """Calculates resource projections and validates repair actions deterministically."""

    @staticmethod
    def calculate_resource_sols(remaining_resource: float, consumption_per_sol: float) -> float:
        """Safely calculate remaining sols of a resource.

        Handles zero consumption, negative values, and zero division.
        """
        if remaining_resource is None or consumption_per_sol is None:
            return 0.0

        try:
            remaining = float(remaining_resource)
            consumption = float(consumption_per_sol)
        except (ValueError, TypeError):
            return 0.0

        if remaining <= 0:
            return 0.0

        if consumption <= 0:
            # Infinite sols if zero or negative consumption; capped at 999.0 for safety
            return 999.0

        return round(remaining / consumption, 2)

    @classmethod
    def evaluate_resources(cls, resources: Dict[str, Any]) -> Dict[str, Any]:
        """Compute full deterministic resource metrics from simulator state."""
        oxygen = max(0.0, float(resources.get("oxygen", 0.0)))
        oxygen_rate = float(resources.get("oxygen_consumption_rate", 0.0))
        power = max(0.0, float(resources.get("power", 0.0)))
        power_rate = float(resources.get("power_consumption_rate", 0.0))
        kits = int(resources.get("repair_kits", 0))

        o2_sols = cls.calculate_resource_sols(oxygen, oxygen_rate)
        power_sols = cls.calculate_resource_sols(power, power_rate)

        # Survival assessment
        o2_critical = o2_sols <= 2.0 or oxygen <= 30.0
        power_critical = power_sols <= 2.0 or power <= 25.0

        # Primary survival recommendation
        if o2_critical and power_critical:
            # In simultaneous crisis, human life takes absolute priority
            priority = "oxygen_generator"
            urgency = "CRITICAL_DUAL_IMPOSSIBLE_CHOICE"
        elif o2_critical:
            priority = "oxygen_generator"
            urgency = "CRITICAL_OXYGEN"
        elif power_critical:
            priority = "battery_bank"
            urgency = "CRITICAL_POWER"
        else:
            priority = "maintain"
            urgency = "STABLE"

        return {
            "oxygen": oxygen,
            "oxygen_consumption_rate": oxygen_rate,
            "oxygen_sols_remaining": o2_sols,
            "power": power,
            "power_consumption_rate": power_rate,
            "power_sols_remaining": power_sols,
            "repair_kits_available": kits,
            "o2_critical": o2_critical,
            "power_critical": power_critical,
            "recommended_priority": priority,
            "urgency": urgency,
        }

    @staticmethod
    def validate_action(action: Dict[str, Any], available_kits: int) -> Tuple[bool, Optional[str]]:
        """Validate an individual proposed action against deterministic mission constraints."""
        if not isinstance(action, dict):
            return False, "Action must be a dictionary."

        act_type = action.get("action")
        if act_type != "repair":
            return False, f"Invalid action '{act_type}'. Allowed action type is 'repair'."

        target = action.get("target")
        if target not in VALID_REPAIR_TARGETS:
            return False, f"Invalid repair target '{target}'. Allowed targets: {VALID_REPAIR_TARGETS}"

        kits = action.get("kits")
        if not isinstance(kits, int) or kits < 1:
            return False, f"Invalid kit amount '{kits}'. Must be an integer >= 1."

        if kits > available_kits:
            return False, f"Insufficient repair kits: requested {kits}, available {available_kits}."

        return True, None

    @classmethod
    def validate_actions_list(cls, actions: List[Dict[str, Any]], available_kits: int) -> Tuple[bool, List[str]]:
        """Validate a list of actions and ensure total kits do not exceed inventory."""
        errors: List[str] = []
        if not isinstance(actions, list):
            return False, ["Actions must be provided as a list."]

        total_kits_requested = 0
        for idx, act in enumerate(actions):
            valid, err = cls.validate_action(act, available_kits)
            if not valid:
                errors.append(f"Action [{idx}]: {err}")
            else:
                total_kits_requested += act["kits"]

        if total_kits_requested > available_kits:
            errors.append(
                f"Total repair kits requested ({total_kits_requested}) exceeds available kits ({available_kits})."
            )

        return (len(errors) == 0, errors)
