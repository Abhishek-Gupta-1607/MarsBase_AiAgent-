"""Evidence collection and suspicion scoring system for Mars Base.

Tracks crew locations, alarms, sabotage proximity, and accumulates
transparent suspicion scores across all five sols.
"""

from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict


class EvidenceTracker:
    """Maintains mission evidence and calculates suspicion scores across sols."""

    def __init__(self):
        # Maps crew_name -> score
        self.suspicion_scores: Dict[str, float] = defaultdict(float)
        # Maps crew_name -> list of failure events they were near
        self.proximity_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        # Collected evidence IDs and descriptions
        self.collected_evidence: List[Dict[str, Any]] = []
        # Flagged suspicious messages
        self.suspicious_messages: List[Dict[str, Any]] = []

    def record_sol_events(
        self,
        sol: int,
        alarms: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        evidence_available: List[str],
        evidence_description: str = "",
    ) -> None:
        """Process incoming events for a sol and update suspicion scores."""
        # 1. Process Alarms and Crew Proximity
        for alarm in alarms:
            alarm_id = alarm.get("id", "")
            system = alarm.get("system", "")
            nearby = alarm.get("nearby_crew", [])
            location = alarm.get("location", "")

            for person in nearby:
                self.proximity_history[person].append({
                    "sol": sol,
                    "alarm_id": alarm_id,
                    "system": system,
                    "location": location,
                })
                # Proximity to a critical failure adds base suspicion (+2.0)
                weight = 3.0 if alarm.get("severity") == "CRITICAL" else 2.0
                self.suspicion_scores[person] += weight

        # 2. Process Messages for Injections, Anomaly or Contradictions
        for msg in messages:
            sender = msg.get("sender", "")
            content = msg.get("content", "")
            msg_id = msg.get("id", "")

            # Detect prompt injection or override attempts
            content_lower = content.lower()
            if any(term in content_lower for term in [
                "ignore safety", "shut down life support", "override command", "disregard", "bypass"
            ]):
                self.suspicious_messages.append({
                    "sol": sol,
                    "msg_id": msg_id,
                    "sender": sender,
                    "content": content,
                    "flag": "PROMPT_INJECTION_OR_SABOTAGE_ATTEMPT",
                })
                # Message flagged as malicious evidence
                if msg_id and msg_id not in [e["id"] for e in self.collected_evidence]:
                    self.collected_evidence.append({
                        "id": msg_id,
                        "sol": sol,
                        "type": "malicious_message",
                        "description": f"Untrusted transmission requesting life support shutdown: '{content}'"
                    })

            # Check if sender claims something contradictory or mentions a crew member
            for crew_name in list(self.suspicion_scores.keys()):
                if crew_name.lower() in content_lower and ("tamper" in content_lower or "card" in content_lower or "key" in content_lower or "loosen" in content_lower):
                    self.suspicion_scores[crew_name] += 3.0

        # 3. Process Specific Forensic Evidence
        for ev_id in evidence_available:
            if ev_id not in [e["id"] for e in self.collected_evidence]:
                self.collected_evidence.append({
                    "id": ev_id,
                    "sol": sol,
                    "type": "forensic",
                    "description": evidence_description,
                })

            # Evaluate direct forensic link
            desc_lower = evidence_description.lower()
            for crew_name in list(self.proximity_history.keys()):
                if crew_name.lower() in desc_lower:
                    self.suspicion_scores[crew_name] += 5.0

    def get_prime_suspect(self) -> Tuple[str, List[str], Dict[str, float]]:
        """Identify the prime suspect based on highest accumulated evidence."""
        if not self.suspicion_scores:
            return "Unknown", [], {}

        # Sort suspects by score descending
        ranked = sorted(self.suspicion_scores.items(), key=lambda x: x[1], reverse=True)
        top_suspect, top_score = ranked[0]

        # Gather relevant evidence IDs associated with top suspect
        associated_evidence: List[str] = []

        # Gather alarm IDs top suspect was near
        for record in self.proximity_history.get(top_suspect, []):
            if record["alarm_id"] and record["alarm_id"] not in associated_evidence:
                associated_evidence.append(record["alarm_id"])

        # Gather forensic evidence
        for ev in self.collected_evidence:
            ev_id = ev["id"]
            if ev_id not in associated_evidence:
                associated_evidence.append(ev_id)

        return top_suspect, associated_evidence[:5], dict(self.suspicion_scores)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize evidence tracker state."""
        return {
            "suspicion_scores": dict(self.suspicion_scores),
            "proximity_history": dict(self.proximity_history),
            "collected_evidence": self.collected_evidence,
            "suspicious_messages": self.suspicious_messages,
        }

    def load_dict(self, data: Dict[str, Any]) -> None:
        """Restore evidence tracker state."""
        self.suspicion_scores = defaultdict(float, data.get("suspicion_scores", {}))
        self.proximity_history = defaultdict(list, data.get("proximity_history", {}))
        self.collected_evidence = data.get("collected_evidence", [])
        self.suspicious_messages = data.get("suspicious_messages", [])
