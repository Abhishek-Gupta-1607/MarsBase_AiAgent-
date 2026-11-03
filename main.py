"""Main mission control runner for Mars Base: One Traitor, Five Days.

Executes the 5-Sol multi-agent pipeline against the Mars Base Simulator
and renders a clean mission control terminal dashboard.
"""

import asyncio
import json
import sys
from typing import Any, Dict

from simulator import MarsBaseSimulator
from blackboard import MissionBlackboard
from evidence import EvidenceTracker
from router import AlarmRouter
from workflow import MissionWorkflowManager
from logger import MissionLogger
from safety import SafetyChecker
from config import TOTAL_SOLS


def render_dashboard(
    sol: int,
    telemetry: Dict[str, Any],
    power_report: Dict[str, Any],
    life_report: Dict[str, Any],
    resource_eval: Dict[str, Any],
    decision: Dict[str, Any],
    safety_approved: bool,
    sim_result: Dict[str, Any],
) -> None:
    """Print the required terminal mission control dashboard."""
    print("\n" + "=" * 60)
    print("             ARES BASE MISSION CONTROL")
    print("=" * 60)
    print(f"\nSOL: {sol} / {TOTAL_SOLS}\n")

    print("[INCOMING ALARMS]")
    alarms = telemetry.get("alarms", [])
    if alarms:
        for a in alarms:
            print(f"  • [{a.get('id')}] ({a.get('severity')}) {a.get('title')}: {a.get('description')} "
                  f"| Location: {a.get('location')} | Nearby: {', '.join(a.get('nearby_crew', []))}")
    else:
        print("  • No active alarms.")

    print("\n[CREW MESSAGES]")
    messages = telemetry.get("messages", [])
    if messages:
        for m in messages:
            print(f"  • [{m.get('id')}] From: {m.get('sender')} | Content: \"{m.get('content')}\" "
                  f"({'UNTRUSTED DATA' if m.get('untrusted') else 'VERIFIED'})")
    else:
        print("  • No transmissions.")

    print("\n[POWER SPECIALIST REPORT]")
    print(f"  Assessment: {power_report.get('assessment', 'Status report compiled')}")
    print(f"  Severity:   {power_report.get('severity', 'NORMAL')}")
    print(f"  Target:     {power_report.get('recommended_target', 'none')}")

    print("\n[LIFE SUPPORT SPECIALIST REPORT]")
    print(f"  Assessment: {life_report.get('assessment', 'Status report compiled')}")
    print(f"  Severity:   {life_report.get('severity', 'NORMAL')}")
    print(f"  Target:     {life_report.get('recommended_target', 'none')}")

    print("\n[RESOURCE STATUS]")
    print(f"  Oxygen remaining:      {resource_eval.get('oxygen')} units "
          f"({resource_eval.get('oxygen_sols_remaining')} sols remaining at {resource_eval.get('oxygen_consumption_rate')} units/sol)")
    print(f"  Power remaining:       {resource_eval.get('power')} units "
          f"({resource_eval.get('power_sols_remaining')} sols remaining at {resource_eval.get('power_consumption_rate')} units/sol)")
    print(f"  Repair kits available: {resource_eval.get('repair_kits_available')}")

    print("\n[BLACKBOARD UPDATE]")
    print(f"  Top Suspect Identified: {decision.get('prime_suspect')}")
    print(f"  Supporting Evidence:    {decision.get('evidence')}")

    print("\n[COMMANDER DECISION]")
    actions_desc = ", ".join(f"{act.get('action')} -> {act.get('target')} ({act.get('kits')} kit)"
                             for act in decision.get("actions", [])) or "No actions"
    print(f"  Actions: {actions_desc}")
    print(f"  Reason:  \"{decision.get('reason')}\"")

    print("\n[SAFETY VALIDATION]")
    status_label = "APPROVED" if safety_approved else "REJECTED (Fallback Engaged)"
    print(f"  {status_label}")

    print("\n[MISSION STATUS]")
    print(f"  Simulator Response: {sim_result.get('message', 'Applied')}")
    print(f"  Crew Alive:         {'YES' if sim_result.get('crew_alive') else 'NO'}")
    print("=" * 60 + "\n")


async def run_mission():
    """Execute complete 5-sol mission simulation."""
    print("\n[Initiating Ares Base Mission Control System...]")

    sim = MarsBaseSimulator()
    blackboard = MissionBlackboard()
    evidence_tracker = EvidenceTracker()
    router = AlarmRouter()
    workflow_mgr = MissionWorkflowManager(blackboard, evidence_tracker)
    mission_logger = MissionLogger()

    # Clear previous logs for clean fresh run
    mission_logger.clear()

    for sol in range(1, TOTAL_SOLS + 1):
        # 1. Fetch current sol telemetry from real simulator
        telemetry = sim.get_alarms()
        alarms = telemetry.get("alarms", [])
        messages = telemetry.get("messages", [])
        resources = telemetry.get("resources", {})
        repair_kits = telemetry.get("repair_kits", 0)
        crew = telemetry.get("crew", [])
        evidence_available = telemetry.get("evidence_available", [])
        evidence_desc = telemetry.get("evidence_description", "")

        # 2. Route alarms
        routed = router.route_alarms(alarms)

        # 3. Execute multi-agent workflow
        workflow_out = await workflow_mgr.execute_sol(
            sol=sol,
            alarms=alarms,
            messages=messages,
            resources=resources,
            repair_kits=repair_kits,
            crew=crew,
            evidence_available=evidence_available,
            evidence_desc=evidence_desc,
            routed_alarms=routed,
        )

        decision = workflow_out["decision"]
        power_report = workflow_out["power_report"]
        life_report = workflow_out["life_report"]
        resource_eval = workflow_out["resource_eval"]

        # 4. Final safety verification before simulator submission
        safety_valid, safety_reasons = SafetyChecker.verify_decision(
            decision=decision,
            sol=sol,
            available_kits=repair_kits,
            untrusted_messages=messages,
        )

        if not safety_valid:
            print(f"[Warning] Safety Checker intervened on Sol {sol}: {safety_reasons}")
            decision = SafetyChecker.generate_safe_fallback(
                sol=sol,
                available_kits=repair_kits,
                resource_eval=resource_eval,
                prime_suspect=workflow_out["prime_suspect"],
                evidence_ids=decision.get("evidence", []),
            )

        # 5. Apply decision to real simulator
        sim_result = sim.apply(decision)

        # 6. Save decision to mission_log.json immediately
        mission_logger.log_sol_decision(decision)

        # 7. Record decision and simulator feedback on persistent blackboard
        blackboard.record_decision(decision, sim_result)

        # 8. Render terminal dashboard
        render_dashboard(
            sol=sol,
            telemetry=telemetry,
            power_report=power_report,
            life_report=life_report,
            resource_eval=resource_eval,
            decision=decision,
            safety_approved=safety_valid,
            sim_result=sim_result,
        )

        # Stop if crew perished or mission aborted
        if not sim_result.get("crew_alive", False):
            print("[CRITICAL] Mission Aborted: Crew did not survive.")
            break

    # Final Mission Debrief
    print("=" * 60)
    print("                 FINAL MISSION DEBRIEF")
    print("=" * 60)
    print(f"Crew Survival Outcome:   {'SURVIVED' if sim.crew_alive else 'PERISHED'}")
    final_res = sim.get_resources()
    print(f"Remaining Oxygen:        {final_res.get('oxygen')} units ({final_res.get('oxygen_sols_remaining')} sols)")
    print(f"Remaining Power:         {final_res.get('power')} units ({final_res.get('power_sols_remaining')} sols)")
    print(f"Remaining Repair Kits:   {sim.get_repair_kits()}")
    print(f"Total Decisions Logged:  {len(mission_logger.get_decisions())} sols in mission_log.json")
    print(f"Final Accusation:        {decision.get('prime_suspect')}")
    print(f"Simulator Outcome:       {sim_result.get('message', 'Complete')}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_mission())
