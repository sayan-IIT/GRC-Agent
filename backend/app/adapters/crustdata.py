import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = logging.getLogger(__name__)


class CrustDataAdapter:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = get_settings().crustdata_base_url

    @retry(wait=wait_exponential(multiplier=0.4, min=0.4, max=2), stop=stop_after_attempt(3), reraise=True)
    async def _call_api(self, vendor_id: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        params = {
            "fields": (
                "company_name,company_id,company_domain,headcount,employee_count,total_investment_usd,"
                "funding_total_usd,total_funding_usd,web_traffic,news_articles,job_openings,"
                "headcount_90d_change_pct,headcount_90days_change_pct,employee_count_90d_change_pct,"
                "web_traffic_90d_change_pct,job_openings_90d_change_pct,latest_funding_round_date"
            )
        }
        if vendor_id.isdigit():
            params["company_id"] = vendor_id
        else:
            params["company_domain"] = vendor_id

        logger.info(f"Calling CrustData API for vendor {vendor_id}")
        async with httpx.AsyncClient(timeout=20) as client:
            request = client.build_request("GET", self.base_url, headers=headers, params=params)
            logger.info("CrustData request URL: %s", request.url)
            response = await client.send(request)
            response.raise_for_status()
            parsed_response = response.json()
            logger.info("CrustData API call succeeded for vendor %s", vendor_id)
            logger.debug("CrustData parsed response: %s", parsed_response)
            return parsed_response

    async def fetch_vendor_signals(self, vendor_id: str) -> dict:
        if not self.api_key:
            logger.error("CRUSTDATA_API_KEY is not set")
            logger.warning("Fallback to mock due to API failure")
            return self._mock_response(vendor_id, "missing_api_key")

        try:
            return await self._call_api(vendor_id)
        except Exception as exc:
            logger.exception("CrustData API call failed for vendor %s: %s", vendor_id, exc)
            logger.warning("Fallback to mock due to API failure")
            return self._mock_response(vendor_id, str(exc))

    def normalize_signals(self, raw_data: dict) -> list:
        company = self._first_company(raw_data)
        now = datetime.now(timezone.utc).isoformat()
        is_mock = bool(raw_data.get("_mock"))
        freshness = 0.65 if is_mock else 1.0

        headcount = self._as_float(company.get("headcount") or company.get("employee_count"), 120.0)
        funding = self._as_float(
            company.get("total_investment_usd")
            or company.get("funding_total_usd")
            or company.get("total_funding_usd"),
            25_000_000.0,
        )
        news_count = len(company.get("news_articles") or [])
        job_count = len(company.get("job_openings") or [])
        headcount_90d_change_pct = self._as_float(
            company.get("headcount_90d_change_pct")
            or company.get("headcount_90days_change_pct")
            or company.get("employee_count_90d_change_pct"),
            0.0,
        )
        web_traffic_90d_change_pct = self._as_float(company.get("web_traffic_90d_change_pct"), 0.0)
        job_openings_90d_change_pct = self._as_float(company.get("job_openings_90d_change_pct"), 0.0)
        vendor_name = company.get("company_name") or company.get("name") or company.get("domain") or "unknown vendor"
        company_domain = company.get("company_domain") or company.get("domain") or company.get("website") or company.get("linkedin_url")

        financial_value = max(0.05, min(0.95, 1 - (funding / 100_000_000)))
        operational_value = max(0.05, min(0.95, 1 - (headcount / 500) + abs(headcount_90d_change_pct) / 200))
        trend_value = max(
            0.05,
            min(
                0.95,
                0.45
                + (news_count * 0.04)
                - (job_count * 0.025)
                + abs(headcount_90d_change_pct) / 250
                + abs(web_traffic_90d_change_pct) / 300,
            ),
        )

        base_confidence = 0.62 if is_mock else 0.8
        signals = [
            {
                "signal_type": "financial_risk",
                "value": round(financial_value, 2),
                "confidence": self._normalize_confidence(base_confidence),
                "timestamp": now,
                "source": "CrustData",
                "freshness": freshness,
                "metadata": {
                    "vendor_name": vendor_name,
                    "vendor_domain": company_domain,
                    "funding_usd": funding,
                    "policy_field": "total_investment_usd",
                    "selected_crustdata_fields": {
                        "company_name": vendor_name,
                        "company_domain": company_domain,
                        "total_investment_usd": funding,
                        "latest_funding_round_date": company.get("latest_funding_round_date"),
                    },
                    "ai_selected_reason": (
                        "Funding is relevant for financial resilience. Recent or substantial funding should lower "
                        "proposed risk because the vendor is more cash rich."
                    ),
                    "api_response_mocked": is_mock,
                },
            },
            {
                "signal_type": "operational_risk",
                "value": round(operational_value, 2),
                "confidence": self._normalize_confidence(base_confidence - 0.05),
                "timestamp": now,
                "source": "CrustData",
                "freshness": freshness,
                "metadata": {
                    "vendor_name": vendor_name,
                    "vendor_domain": company_domain,
                    "headcount": headcount,
                    "headcount_90d_change_pct": headcount_90d_change_pct,
                    "policy_field": "headcount",
                    "selected_crustdata_fields": {
                        "company_name": vendor_name,
                        "company_domain": company_domain,
                        "headcount": headcount,
                        "headcount_90d_change_pct": headcount_90d_change_pct,
                    },
                    "ai_selected_reason": (
                        "Headcount and 90-day headcount movement are relevant to operating scale. A sharp increase "
                        "or decrease in the last 30-90 days should increase proposed risk because it can signal "
                        "execution volatility, reorganization, or scaling pressure."
                    ),
                    "api_response_mocked": is_mock,
                },
            },
            {
                "signal_type": "trend_risk",
                "value": round(trend_value, 2),
                "confidence": self._normalize_confidence(base_confidence - 0.08),
                "timestamp": now,
                "source": "CrustData",
                "freshness": freshness,
                "metadata": {
                    "vendor_name": vendor_name,
                    "vendor_domain": company_domain,
                    "news_articles": news_count,
                    "job_openings": job_count,
                    "headcount_90d_change_pct": headcount_90d_change_pct,
                    "web_traffic_90d_change_pct": web_traffic_90d_change_pct,
                    "job_openings_90d_change_pct": job_openings_90d_change_pct,
                    "policy_field": "news_articles/job_openings",
                    "selected_crustdata_fields": {
                        "company_name": vendor_name,
                        "company_domain": company_domain,
                        "news_article_count": news_count,
                        "job_opening_count": job_count,
                        "headcount_90d_change_pct": headcount_90d_change_pct,
                        "web_traffic_90d_change_pct": web_traffic_90d_change_pct,
                        "job_openings_90d_change_pct": job_openings_90d_change_pct,
                    },
                    "ai_selected_reason": (
                        "Recent company activity and 90-day movement metrics are relevant to trend risk. Falling "
                        "traffic or hiring contraction should increase proposed risk; healthy hiring and traffic "
                        "momentum can reduce concern."
                    ),
                    "api_response_mocked": is_mock,
                },
            },
        ]
        logger.info("Normalized %s CrustData signals", len(signals))
        return signals

    def _first_company(self, raw_data: dict) -> dict[str, Any]:
        if isinstance(raw_data.get("data"), list) and raw_data["data"]:
            return raw_data["data"][0]
        if isinstance(raw_data.get("results"), list) and raw_data["results"]:
            return raw_data["results"][0]
        if isinstance(raw_data, list) and raw_data:
            return raw_data[0]
        return raw_data

    def _normalize_confidence(self, value: float) -> float:
        return round(max(0.0, min(1.0, value)), 2)

    def _as_float(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _mock_response(self, vendor_id: str, reason: str) -> dict[str, Any]:
        vendor_fixtures = {
            "hilberts.ai": {
                "company_name": "Hilbert",
                "company_domain": "hilberts.ai",
                "company_id": "mock-hilbert",
                "headcount": 42,
                "headcount_90d_change_pct": 18.0,
                "total_investment_usd": 28_000_000,
                "latest_funding_round_date": "2026-04-15",
                "web_traffic_90d_change_pct": 24.0,
                "job_openings_90d_change_pct": 12.0,
                "news_articles": [{"title": "Hilbert raises $28M Series A led by a16z"}],
                "job_openings": [{"title": "Enterprise AI engineer"}],
            },
            "thinkingmachines.ai": {
                "company_name": "Thinking Machines Lab",
                "company_domain": "thinkingmachines.ai",
                "company_id": "mock-thinking-machines",
                "headcount": 130,
                "headcount_90d_change_pct": 32.0,
                "total_investment_usd": 2_000_000_000,
                "latest_funding_round_date": "2025-07-15",
                "web_traffic_90d_change_pct": 41.0,
                "job_openings_90d_change_pct": 25.0,
                "news_articles": [{"title": "Thinking Machines Lab talent and funding update"}],
                "job_openings": [{"title": "Research engineer"}, {"title": "Infrastructure engineer"}],
            },
            "block.xyz": {
                "company_name": "Block Inc.",
                "company_domain": "block.xyz",
                "company_id": "mock-block",
                "headcount": 12_000,
                "headcount_90d_change_pct": -4.0,
                "total_investment_usd": 0,
                "latest_funding_round_date": None,
                "web_traffic_90d_change_pct": -3.0,
                "job_openings_90d_change_pct": -9.0,
                "news_articles": [{"title": "Block payments platform operating update"}],
                "job_openings": [{"title": "Risk operations lead"}, {"title": "Payments compliance counsel"}],
            },
        }
        return {
            "_mock": True,
            "_fallback_reason": reason,
            "data": [vendor_fixtures.get(vendor_id, {
                "company_name": vendor_id,
                "company_id": "mock-crustdata-company",
                "headcount": 96,
                "total_investment_usd": 18_500_000,
                "news_articles": [{"title": "Supplier faces margin pressure"}],
                "job_openings": [],
            })],
        }
