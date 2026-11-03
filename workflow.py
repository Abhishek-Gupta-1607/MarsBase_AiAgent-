"""Multi-Agent Mission Control Workflow using Agent Framework.

Implements:
- Router (switch-case edges)
- Fan-out to Power Specialist and Life Support Specialist running concurrently
- Fan-in synchronization barrier waiting for both specialists
- Blackboard state management (ctx.set_state / ctx.get_state) with independent keys
- Commander synthesis with Safety Checker review
"""

import json
from typing import Any, Dict, List
from agent_framework import WorkflowBuilder, WorkflowContext, executor
from agents import power_agent, life_support_agent, ask
from blackboard import MissionBlackboard
from commander import CommanderCoordinator
from rules import PythonRuleChecker
from evidence import EvidenceTracker


# ==============================================================================
# Executors for Graph Workflow
# ==============================================================================

@executor(id="dispatch_mission_data")
async def dispatch_mission_data(input_data: Dict[str, Any], ctx: WorkflowContext[str]) -> None:
    """Intake node: initializes sol state on the blackboard and triggers parallel analysis."""
    sol = input_data["sol"]
    alarms = input_data["alarms"]
    messages = input_data["messages"]
    resources = input_data["resources"]
    routed = input_data["routed"]

    # Store on WorkflowContext blackboard using unique keys
    ctx.set_state("sol", sol)
    ctx.set_state("alarms", alarms)
    ctx.set_state("messages", messages)
    ctx.set_state("resources", resources)
    ctx.set_state("power_alarms", routed.get("power", []))
    ctx.set_state("life_alarms", routed.get("life_support", []))
    ctx.set_state("general_alarms", routed.get("general", []))

    # Fan out to specialists
    await ctx.send_message("analyze")


@executor(id="analyze_power")
async def analyze_power(_: str, ctx: WorkflowContext[str]) -> None:
    """Power Specialist executor running in parallel."""
    sol = ctx.get_state("sol")
    power_alarms = ctx.get_state("power_alarms")
    resources = ctx.get_state("resources")

    prompt = f"""[POWER ANALYSIS - SOL {sol}]
Current Power Level: {resources.get('power')} units
Current Power Consumption: {resources.get('power_consumption_rate')} units/sol
Assigned Power Alarms:
{json.dumps(power_alarms, indent=2)}

Provide your diagnosis in the required JSON format.
"""
    try:
        raw_report = await ask(power_agent, prompt)
        clean = raw_report.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:-1]).strip()
        report = json.loads(clean)
    except Exception as e:
        report = {
            "system": "power",
            "status": "FAILED",
            "error": str(e),
            "severity": "HIGH",
            "recommended_target": "battery_bank",
            "kits_required": 1,
        }

    # Store in dedicated blackboard key
    ctx.set_state("power_report", report)
    await ctx.send_message("power_done")


@executor(id="analyze_life_support")
async def analyze_life_support(_: str, ctx: WorkflowContext[str]) -> None:
    """Life Support Specialist executor running in parallel."""
    sol = ctx.get_state("sol")
    life_alarms = ctx.get_state("life_alarms")
    resources = ctx.get_state("resources")

    prompt = f"""[LIFE SUPPORT ANALYSIS - SOL {sol}]
Current Oxygen Level: {resources.get('oxygen')} units
Current Oxygen Consumption: {resources.get('oxygen_consumption_rate')} units/sol
Assigned Life Support Alarms:
{json.dumps(life_alarms, indent=2)}

Provide your diagnosis in the required JSON format.
"""
    try:
        raw_report = await ask(life_support_agent, prompt)
        clean = raw_report.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:-1]).strip()
        report = json.loads(clean)
    except Exception as e:
        report = {
            "system": "life_support",
            "status": "FAILED",
            "error": str(e),
            "severity": "CRITICAL",
            "recommended_target": "oxygen_generator",
            "kits_required": 1,
        }

    # Store in dedicated blackboard key
    ctx.set_state("life_report", report)
    await ctx.send_message("life_done")


@executor(id="fan_in_barrier")
async def fan_in_barrier(findings: List[str], ctx: WorkflowContext) -> None:
    """Fan-in barrier executor: runs ONLY after BOTH specialists have completed."""
    # Ensure both reports are present on the blackboard
    power_report = ctx.get_state("power_report")
    life_report = ctx.get_state("life_report")

    if not power_report or not life_report:
        raise RuntimeError("Fan-in synchronization error: One or more specialist reports missing.")

    combined = {
        "status": "FAN_IN_COMPLETE",
        "power_report": power_report,
        "life_report": life_report,
        "signals": findings,
    }
    await ctx.yield_output(combined)


SPECIALISTS = [analyze_power, analyze_life_support]


def build_specialist_workflow():
    """Build fan-out/fan-in workflow graph for parallel specialist analysis."""
    return (
        WorkflowBuilder(start_executor=dispatch_mission_data)
        .add_fan_out_edges(dispatch_mission_data, SPECIALISTS)
        .add_fan_in_edges(SPECIALISTS, fan_in_barrier)
        .build()
    )


class MissionWorkflowManager:
    """Orchestrates sol workflow execution across all system components."""

    def __init__(self, blackboard: MissionBlackboard, evidence_tracker: EvidenceTracker):
        self.blackboard = blackboard
        self.evidence_tracker = evidence_tracker
        self.specialist_flow = build_specialist_workflow()

    async def execute_sol(
        self,
        sol: int,
        alarms: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        resources: Dict[str, Any],
        repair_kits: int,
        crew: List[Dict[str, Any]],
        evidence_available: List[str],
        evidence_desc: str,
        routed_alarms: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Execute the full multi-agent pipeline for a single sol."""
        # 1. Update shared blackboard and evidence tracker
        self.blackboard.update_for_sol(
            sol=sol,
            alarms=alarms,
            messages=messages,
            repair_kits=repair_kits,
            crew=crew,
            evidence_available=evidence_available,
        )
        self.evidence_tracker.record_sol_events(
            sol=sol,
            alarms=alarms,
            messages=messages,
            evidence_available=evidence_available,
            evidence_description=evidence_desc,
        )

        # 2. Run Parallel Specialist Workflow (Fan-out / Fan-in)
        flow_input = {
            "sol": sol,
            "alarms": alarms,
            "messages": messages,
            "resources": resources,
            "routed": routed_alarms,
        }
        flow_result = await self.specialist_flow.run(flow_input)
        specialist_outputs = flow_result.get_outputs()[0]
        power_report = specialist_outputs["power_report"]
        life_report = specialist_outputs["life_report"]

        # Persist reports into blackboard
        self.blackboard.data["power_report"] = power_report
        self.blackboard.data["life_report"] = life_report

        # 3. Deterministic Python Rule Calculations
        resource_eval = PythonRuleChecker.evaluate_resources(resources)

        # 4. Evidence and Suspicion Evaluation
        prime_suspect, top_evidence, suspicion_ranking = self.evidence_tracker.get_prime_suspect()
        self.blackboard.data["suspect_scores"] = suspicion_ranking

        # 5. Commander Decision Formulation with Safety Checker Review Loop
        decision = await CommanderCoordinator.decide_with_review(
            sol=sol,
            alarms=alarms,
            messages=messages,
            power_report=power_report,
            life_report=life_report,
            resource_eval=resource_eval,
            prime_suspect=prime_suspect,
            evidence_ids=top_evidence,
            suspicion_ranking=suspicion_ranking,
        )

        return {
            "decision": decision,
            "power_report": power_report,
            "life_report": life_report,
            "resource_eval": resource_eval,
            "prime_suspect": prime_suspect,
            "suspicion_ranking": suspicion_ranking,
        }
