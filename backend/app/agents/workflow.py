import logging
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.config import get_settings

logger = logging.getLogger(__name__)


class RiskWorkflowState(TypedDict, total=False):
    risk_id: str
    risk_name: str
    current_score: float
    internal_score: float
    manual_score: float
    signals: list[dict[str, Any]]
    structured_signals: list[dict[str, Any]]
    scoring: dict[str, Any]
    explanation: dict[str, Any]
    audit_record: dict[str, Any]


def signal_agent(state: RiskWorkflowState) -> RiskWorkflowState:
    signals = state.get("signals", [])
    structured = [
        {
            **signal,
            "source": signal.get("source", "internal"),
            "confidence": max(0.0, min(1.0, float(signal.get("confidence", 0.5)))),
        }
        for signal in signals
    ]
    logger.info("Signal Agent structured %s signals", len(structured))
    return {"structured_signals": structured}


def scoring_agent(state: RiskWorkflowState) -> RiskWorkflowState:
    signals = state.get("structured_signals", [])
    external_values = [float(s["value"]) for s in signals if s.get("source") == "CrustData"]
    avg_external = sum(external_values) / len(external_values) if external_values else 0.5
    trend = max(external_values) - min(external_values) if len(external_values) > 1 else avg_external
    internal = float(state.get("internal_score", state.get("current_score", 5.0) / 10))
    manual = float(state.get("manual_score", 0.5))

    weighted = (0.4 * internal) + (0.3 * avg_external) + (0.2 * trend) + (0.1 * manual)
    proposed_score = round(max(0, min(10, weighted * 10)), 1)
    confidence = round(sum(float(s.get("confidence", 0.5)) for s in signals) / len(signals), 2) if signals else 0.5

    scoring = {"proposed_score": proposed_score, "confidence": confidence}
    logger.info("Scoring Agent proposed %s with confidence %s", proposed_score, confidence)
    return {"scoring": scoring}


def explanation_agent(state: RiskWorkflowState) -> RiskWorkflowState:
    scoring = state["scoring"]
    signals = state.get("structured_signals", [])
    crust_signals = [s for s in signals if s.get("source") == "CrustData"]
    top = sorted(crust_signals, key=lambda s: s.get("value", 0), reverse=True)[:2]
    key_drivers = [f"{s['signal_type']}={s['value']} from CrustData" for s in top]
    direction = "increase" if scoring["proposed_score"] > state.get("current_score", 0) else "decrease"
    evidence = [
        f"CrustData signal {s['signal_type']} reported value {s['value']} at confidence {s['confidence']}"
        for s in top
    ]
    explanation = {
        "summary": f"AI suggested a risk {direction} for {state.get('risk_name')} based on external CrustData signals.",
        "key_drivers": key_drivers,
        "evidence": evidence,
        "confidence": scoring["confidence"],
    }
    logger.info("Explanation Agent generated evidence citing CrustData")
    return {"explanation": explanation}


def audit_agent(state: RiskWorkflowState) -> RiskWorkflowState:
    audit_record = {
        "previous_score": state.get("current_score"),
        "proposed_score": state["scoring"]["proposed_score"],
        "source": "CrustData",
        "signals_used": state.get("structured_signals", []),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_version": get_settings().model_version,
    }
    logger.info("Audit Agent prepared immutable score proposal record")
    return {"audit_record": audit_record}


def build_risk_workflow():
    graph = StateGraph(RiskWorkflowState)
    graph.add_node("signal_agent", signal_agent)
    graph.add_node("scoring_agent", scoring_agent)
    graph.add_node("explanation_agent", explanation_agent)
    graph.add_node("audit_agent", audit_agent)
    graph.set_entry_point("signal_agent")
    graph.add_edge("signal_agent", "scoring_agent")
    graph.add_edge("scoring_agent", "explanation_agent")
    graph.add_edge("explanation_agent", "audit_agent")
    graph.add_edge("audit_agent", END)
    return graph.compile()

