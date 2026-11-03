"""Mission logger for persisting decisions to mission_log.json after each sol.

Ensures safe atomic file writing and continuous persistence.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from config import MISSION_LOG_PATH


class MissionLogger:
    """Manages appending and persisting decisions to mission_log.json."""

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or MISSION_LOG_PATH
        self.decisions: List[Dict[str, Any]] = []
        self._load_existing()

    def _load_existing(self) -> None:
        """Load any existing decisions from file."""
        if self.log_path.exists():
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.decisions = data
            except Exception:
                self.decisions = []

    def log_sol_decision(self, decision: Dict[str, Any]) -> None:
        """Append decision for the current sol and immediately save to disk."""
        # Replace if this sol already exists (e.g. on rerun), otherwise append
        sol = decision.get("sol")
        existing_idx = next((i for i, d in enumerate(self.decisions) if d.get("sol") == sol), None)
        if existing_idx is not None:
            self.decisions[existing_idx] = decision
        else:
            self.decisions.append(decision)

        # Sort by sol
        self.decisions.sort(key=lambda d: d.get("sol", 0))

        # Save to disk immediately
        self.save()

    def save(self) -> None:
        """Safely write decisions to file."""
        try:
            with open(self.log_path, "w", encoding="utf-8") as f:
                json.dump(self.decisions, f, indent=4)
        except Exception as e:
            print(f"[Error] Failed to write mission log: {e}")

    def get_decisions(self) -> List[Dict[str, Any]]:
        """Return all logged decisions."""
        return list(self.decisions)

    def clear(self) -> None:
        """Clear log file and in-memory entries."""
        self.decisions = []
        if self.log_path.exists():
            try:
                self.log_path.unlink()
            except Exception:
                pass
