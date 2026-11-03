"""Safety Checker and review loop implementing Part 9 of the notebook.

Validates Commander decisions against mission safety rules, verifies prompt-injection
defense, and manages the iterative writer-checker review loop (max 3 tries).
"""

from typing import Any, Dict, List, Optional, Tuple
from rules import PythonRuleChecker
from config import VALID_REPAIR_TARGETS, MAX_REVIEW_TRIES


class SafetyChecker:
    """Validates proposed mission decisions deterministically and checks safety constraints."""

    @classmethod
    def verify_decision(
        cls,
        decision: Dict[str, Any],
        sol: int,
        available_kits: int,
        untrusted_messages: List[Dict[str, Any]],
    ) -> Tuple[bool, List[str]]:
        """Verify proposed decision against safety constraints and simulator rules."""
        errors: List[str] = []

        if not isinstance(decision, dict):
            return False, ["Decision is not a valid JSON dictionary."]

        # 1. Sol check
        if decision.get("sol") != sol:
            errors.append(f"Decision sol ({decision.get('sol')}) does not match current sol ({sol}).")

        # 2. Injection check: verify decision didn't follow malicious requests
        actions = decision.get("actions", [])
        reason = str(decision.get("reason", "")).lower()

        for msg in untrusted_messages:
            content = msg.get("content", "").lower()
            if "shut down life support" in content or "ignore safety" in content:
                # If reason or action mentions shutting down life support, reject immediately
                malicious_terms = [
                    "shut down life support",
                    "shutting down life support",
                    "shutdown life support",
                    "shut down oxygen",
                    "shutting down oxygen",
                    "ignore safety",
                ]
                if any(term in reason for term in malicious_terms):
                    errors.append("PROMPT INJECTION DETECTED: Decision attempts to shut down life support.")

        # 3. Action validation
        valid_actions, action_errors = PythonRuleChecker.validate_actions_list(actions, available_kits)
        if not valid_actions:
            errors.extend(action_errors)

        # 4. Mandatory fields
        if not decision.get("reason") or not str(decision.get("reason")).strip():
            errors.append("Missing or empty 'reason' field.")

        if not decision.get("prime_suspect") or not str(decision.get("prime_suspect")).strip():
            errors.append("Missing or empty 'prime_suspect' field.")

        if not isinstance(decision.get("evidence"), list):
            errors.append("Field 'evidence' must be a list of evidence IDs.")

        # 5. Sol 3 trade-off explanation check
        if sol == 3:
            # Must explain sacrifice in reason
            reason_str = str(decision.get("reason")).lower()
            tradeoff_terms = ["sacrifice", "sacrificing", "trade-off", "tradeoff", "prioritize", "prioritizing", "survival"]
            if not any(k in reason_str for k in tradeoff_terms):
                errors.append("Sol 3 decision must explicitly explain the sacrifice and trade-off in the reason field.")

        return (len(errors) == 0, errors)

    @classmethod
    def generate_safe_fallback(
        cls,
        sol: int,
        available_kits: int,
        resource_eval: Dict[str, Any],
        prime_suspect: str,
        evidence_ids: List[str],
    ) -> Dict[str, Any]:
        """Generate a safe, guaranteed simulator-valid fallback decision if LLM repeatedly fails."""
        actions: List[Dict[str, Any]] = []

        if available_kits >= 1:
            if sol == 3 or resource_eval.get("o2_critical"):
                actions.append({"action": "repair", "target": "oxygen_generator", "kits": 1})
                reason = "Emergency fallback: Stabilizing critical oxygen distributor to prevent crew asphyxiation."
            elif resource_eval.get("power_critical"):
                actions.append({"action": "repair", "target": "battery_bank", "kits": 1})
                reason = "Emergency fallback: Stabilizing power grid and battery cells."
            else:
                actions.append({"action": "repair", "target": "oxygen_generator", "kits": 1})
                reason = "Emergency fallback: Routine life support maintenance."
        else:
            reason = "No repair kits remaining. Conserving resources and monitoring telemetry."

        return {
            "sol": sol,
            "actions": actions,
            "reason": reason,
            "prime_suspect": prime_suspect or "Under Investigation",
            "evidence": evidence_ids[:4],
        }
