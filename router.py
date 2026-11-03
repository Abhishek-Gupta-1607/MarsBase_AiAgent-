"""Alarm Router implementing the professor's routing concepts.

Uses WorkflowBuilder, add_switch_case_edge_group, Case, and Default.
Classifies incoming alarms into 'power', 'life_support', or 'general' without
discarding any alarm.
"""

from dataclasses import dataclass
from typing import Any, Dict, List
from agent_framework import WorkflowBuilder, WorkflowContext, executor, Case, Default


@dataclass
class RoutedAlarm:
    alarm_id: str
    title: str
    description: str
    category: str  # "power" | "life_support" | "general"
    raw_alarm: Dict[str, Any]


def classify_alarm(alarm: Dict[str, Any]) -> str:
    """Classify an alarm into power, life_support, or general queue based on system and keywords."""
    system = alarm.get("system", "").lower()
    text = (alarm.get("title", "") + " " + alarm.get("description", "")).lower()

    # Power keywords
    power_keywords = ("power", "battery", "solar", "volt", "electrical", "grid", "thermal", "overheat", "bus")
    # Life support keywords
    life_keywords = ("oxygen", "o2", "pressure", "scrubber", "air", "ventilation", "atmosphere", "life_support", "asphyxiate")

    if system == "power" or any(k in text for k in power_keywords):
        return "power"
    if system == "life_support" or any(k in text for k in life_keywords):
        return "life_support"
    return "general"


class AlarmRouter:
    """Routes incoming alarms to respective queues while maintaining an audit record."""

    def __init__(self):
        self.power_queue: List[Dict[str, Any]] = []
        self.life_queue: List[Dict[str, Any]] = []
        self.general_queue: List[Dict[str, Any]] = []
        self.routing_record: List[RoutedAlarm] = []

    def route_alarms(self, alarms: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Classify and partition alarms into appropriate specialist queues."""
        self.power_queue.clear()
        self.life_queue.clear()
        self.general_queue.clear()
        self.routing_record.clear()

        for a in alarms:
            category = classify_alarm(a)
            routed = RoutedAlarm(
                alarm_id=a.get("id", "unknown"),
                title=a.get("title", ""),
                description=a.get("description", ""),
                category=category,
                raw_alarm=a,
            )
            self.routing_record.append(routed)

            if category == "power":
                self.power_queue.append(a)
            elif category == "life_support":
                self.life_queue.append(a)
            else:
                self.general_queue.append(a)

        return {
            "power": list(self.power_queue),
            "life_support": list(self.life_queue),
            "general": list(self.general_queue),
            "all_count": len(alarms),
            "routed_count": len(self.routing_record),
        }


# ==============================================================================
# Agent Framework Graph Router Construction
# ==============================================================================

@executor(id="classify_executor")
async def classify_executor(alarm: Dict[str, Any], ctx: WorkflowContext[RoutedAlarm]) -> None:
    category = classify_alarm(alarm)
    routed = RoutedAlarm(
        alarm_id=alarm.get("id", "unknown"),
        title=alarm.get("title", ""),
        description=alarm.get("description", ""),
        category=category,
        raw_alarm=alarm,
    )
    await ctx.send_message(routed)


@executor(id="power_desk")
async def power_desk(r: RoutedAlarm, ctx: WorkflowContext) -> None:
    await ctx.yield_output({"desk": "power", "alarm": r.raw_alarm})


@executor(id="life_support_desk")
async def life_support_desk(r: RoutedAlarm, ctx: WorkflowContext) -> None:
    await ctx.yield_output({"desk": "life_support", "alarm": r.raw_alarm})


@executor(id="general_desk")
async def general_desk(r: RoutedAlarm, ctx: WorkflowContext) -> None:
    await ctx.yield_output({"desk": "general", "alarm": r.raw_alarm})


def build_alarm_router_flow():
    """Build WorkflowBuilder graph using switch-case edge groups, Case and Default."""
    return (
        WorkflowBuilder(start_executor=classify_executor)
        .add_switch_case_edge_group(classify_executor, [
            Case(condition=lambda r: r.category == "power", target=power_desk),
            Case(condition=lambda r: r.category == "life_support", target=life_support_desk),
            Default(target=general_desk),
        ])
        .build()
    )
