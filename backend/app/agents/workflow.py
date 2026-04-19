import logging
import json
from datetime import datetime, timezone
from typing import Any, TypedDict

import httpx
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

    scoring = {
        "proposed_score": proposed_score,
        "confidence": confidence,
        "breakdown": {
            "internal_component": round(0.4 * internal * 10, 2),
            "crustdata_external_component": round(0.3 * avg_external * 10, 2),
            "trend_component": round(0.2 * trend * 10, 2),
            "manual_component": round(0.1 * manual * 10, 2),
            "average_crustdata_signal": round(avg_external, 2),
            "trend_signal_range": round(trend, 2),
        },
    }
    logger.info("Scoring Agent proposed %s with confidence %s", proposed_score, confidence)
    return {"scoring": scoring}


async def explanation_agent(state: RiskWorkflowState) -> RiskWorkflowState:
    scoring = state["scoring"]
    signals = state.get("structured_signals", [])
    crust_signals = [s for s in signals if s.get("source") == "CrustData"]
    top = sorted(crust_signals, key=lambda s: s.get("value", 0), reverse=True)
    direction = "increase" if scoring["proposed_score"] > state.get("current_score", 0) else "decrease"
    current_score = float(state.get("current_score", 0))
    breakdown = scoring["breakdown"]

    selected_evidence = [_selected_evidence(signal) for signal in top]
    summary = await _llm_summary(
        risk_name=str(state.get("risk_name")),
        current_score=current_score,
        proposed_score=scoring["proposed_score"],
        direction=direction,
        evidence=selected_evidence,
        breakdown=breakdown,
        confidence=scoring["confidence"],
    )
    explanation = {
        "summary": summary,
        "analysis_method": (
            "The explanation agent reviewed the vendor-specific CrustData response, selected only fields "
            "material to each risk dimension, and combined those fields with internal posture, trend, and "
            "manual review inputs. Score components: internal="
            f"{breakdown['internal_component']}, external CrustData={breakdown['crustdata_external_component']}, "
            f"trend={breakdown['trend_component']}, manual={breakdown['manual_component']}."
        ),
        "key_drivers": [_driver_text(signal) for signal in top],
        "evidence": [_evidence_text(signal) for signal in top],
        "confidence": scoring["confidence"],
    }
    logger.info("Explanation Agent generated evidence citing CrustData")
    return {"explanation": explanation}


async def _llm_summary(
    risk_name: str,
    current_score: float,
    proposed_score: float,
    direction: str,
    evidence: list[dict[str, Any]],
    breakdown: dict[str, Any],
    confidence: float,
) -> str:
    settings = get_settings()
    if settings.google_ai_api_key:
        try:
            prompt = (
                "You are a GRC risk analyst. Produce a concise, investor-demo ready explanation. "
                "Use only the provided CrustData-selected fields and score components. Do not invent policy names.\n\n"
                "Risk logic to apply:\n"
                "- Funding or a recent funding round should decrease proposed risk because the vendor is more cash rich.\n"
                "- Large headcount changes in the last 30 or 90 days should increase proposed risk because they can indicate "
                "scaling strain, restructuring, or operating volatility.\n"
                "- Negative hiring, web traffic, payment, or credit movement should increase proposed risk.\n"
                "- Format the answer exactly with sections named Reason, Impact, and Confidence.\n"
                "- Under Reason, use bullet points and cite CrustData field names and values.\n\n"
                f"Risk: {risk_name}\n"
                f"Current score: {current_score:.1f}\n"
                f"Proposed score: {proposed_score:.1f}\n"
                f"Direction: {direction}\n"
                f"Confidence: {confidence}\n"
                f"Score components: {json.dumps(breakdown, default=str)}\n"
                f"Selected CrustData evidence: {json.dumps(evidence, default=str)}\n\n"
                "Write a short explanation like:\n"
                "Reason:\n"
                "- Vendor credit score dropped from 720 to 640 (Source: CrustData)\n"
                "- 3 late payments reported in last 30 days\n\n"
                "Impact:\n"
                "- Increased likelihood of supplier disruption\n\n"
                "Confidence:\n"
                f"- Medium ({confidence})"
            )
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{settings.google_ai_model}:generateContent"
            )
            headers = {
                "x-goog-api-key": settings.google_ai_api_key,
                "Content-Type": "application/json",
            }
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}],
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 360,
                },
            }
            async with httpx.AsyncClient(timeout=25) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                parsed = response.json()
            text = _extract_gemini_text(parsed)
            if text:
                logger.info("Gemini explanation generated with Google AI Studio model %s", settings.google_ai_model)
                return text
            logger.warning("Gemini response did not include text; using local explanation agent fallback")
        except Exception as exc:
            logger.warning("Google AI Studio explanation failed; using local explanation agent fallback: %s", exc)

    evidence_text = "; ".join(_compact_evidence(e) for e in evidence)
    return (
        "Reason:\n"
        f"- Proposed risk should {direction} for {risk_name}, moving from {current_score:.1f} to "
        f"{proposed_score:.1f}.\n"
        f"- The agent selected CrustData fields that match the risk dimensions: {evidence_text}.\n"
        "- Recent funding lowers financial risk because the vendor is more cash rich; sharp 30-90 day "
        "headcount movement increases operational risk because it can signal scaling strain or restructuring.\n\n"
        "Impact:\n"
        f"- The final score combines internal posture={breakdown['internal_component']}, external CrustData="
        f"{breakdown['crustdata_external_component']}, trend={breakdown['trend_component']}, and manual="
        f"{breakdown['manual_component']} to prioritize human review before approval.\n\n"
        "Confidence:\n"
        f"- Medium ({confidence}), based on CrustData signal confidence and freshness normalization."
    )


def _selected_evidence(signal: dict[str, Any]) -> dict[str, Any]:
    metadata = signal.get("metadata", {})
    return {
        "signal_type": signal.get("signal_type"),
        "signal_value": signal.get("value"),
        "confidence": signal.get("confidence"),
        "freshness": signal.get("freshness"),
        "selected_fields": metadata.get("selected_crustdata_fields", {}),
        "why_selected": metadata.get("ai_selected_reason"),
        "source_mode": "fallback mock" if metadata.get("api_response_mocked") else "live CrustData API",
    }


def _extract_gemini_text(parsed_response: dict[str, Any]) -> str:
    candidates = parsed_response.get("candidates") or []
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts") or []
    text_parts = [part.get("text", "") for part in parts if isinstance(part, dict)]
    return "\n".join(part for part in text_parts if part).strip()


def _driver_text(signal: dict[str, Any]) -> str:
    metadata = signal.get("metadata", {})
    vendor_name = metadata.get("vendor_name", "vendor")
    vendor_domain = metadata.get("vendor_domain")
    vendor_label = f"{vendor_name} ({vendor_domain})" if vendor_domain else vendor_name
    selected_fields = metadata.get("selected_crustdata_fields", {})
    reason = metadata.get("ai_selected_reason", "Selected as relevant evidence for this signal.")
    if signal["signal_type"] == "financial_risk":
        funding = _money(metadata.get("funding_usd"))
        return (
            f"{vendor_label}: financial_risk={signal['value']} because selected CrustData funding evidence "
            f"shows total_investment_usd={funding}. {reason}"
        )
    if signal["signal_type"] == "operational_risk":
        return (
            f"{vendor_label}: operational_risk={signal['value']} because selected CrustData operating evidence "
            f"shows headcount={selected_fields.get('headcount', 'unknown')} and "
            f"headcount_90d_change_pct={selected_fields.get('headcount_90d_change_pct', 'unknown')}. {reason}"
        )
    return (
        f"{vendor_label}: trend_risk={signal['value']} because selected CrustData activity evidence shows "
        f"news_article_count={selected_fields.get('news_article_count', 0)}, "
        f"job_opening_count={selected_fields.get('job_opening_count', 0)}, "
        f"web_traffic_90d_change_pct={selected_fields.get('web_traffic_90d_change_pct', 0)}."
    )


def _evidence_text(signal: dict[str, Any]) -> str:
    mocked = signal.get("metadata", {}).get("api_response_mocked")
    data_mode = "fallback mock after API failure" if mocked else "live API response"
    selected_fields = signal.get("metadata", {}).get("selected_crustdata_fields", {})
    reason = signal.get("metadata", {}).get("ai_selected_reason")
    return (
        f"CrustData {data_mode} produced {signal['signal_type']} value {signal['value']} "
        f"with confidence {signal['confidence']} and freshness {signal.get('freshness', 1.0)}. "
        f"AI-selected fields: {selected_fields}. Reason: {reason}"
    )


def _compact_evidence(evidence: dict[str, Any]) -> str:
    return (
        f"{evidence['signal_type']}={evidence['signal_value']} from "
        f"{evidence['selected_fields']} (Source: CrustData; {evidence['why_selected']})"
    )


def _money(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.1f}B"
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    return f"${amount:,.0f}"


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
