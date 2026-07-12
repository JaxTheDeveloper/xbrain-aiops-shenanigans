from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ServiceReliabilityPolicy:
    service_name: str
    availability_slo: float
    latency_slo: float
    monthly_requests: int
    monthly_error_budget_minutes: float
    fast_burn_threshold: float
    slow_burn_threshold: float


def build_policy(service_name: str, monthly_requests: int, availability_slo: float = 0.999, latency_slo: float = 0.995) -> ServiceReliabilityPolicy:
    error_budget_fraction = 1 - availability_slo
    allowed_failures = monthly_requests * error_budget_fraction
    monthly_error_budget_minutes = (allowed_failures / max(monthly_requests, 1)) * 30 * 24 * 60
    return ServiceReliabilityPolicy(
        service_name=service_name,
        availability_slo=availability_slo,
        latency_slo=latency_slo,
        monthly_requests=monthly_requests,
        monthly_error_budget_minutes=monthly_error_budget_minutes,
        fast_burn_threshold=14.4,
        slow_burn_threshold=6.0,
    )


def classify_burn_rate(burn_rate: float) -> str:
    if burn_rate >= 14.4:
        return "fast-burn"
    if burn_rate >= 6.0:
        return "slow-burn"
    return "normal"


def summarize_policy(policy: ServiceReliabilityPolicy) -> dict:
    return {
        "service": policy.service_name,
        "availability_slo": policy.availability_slo,
        "latency_slo": policy.latency_slo,
        "monthly_requests": policy.monthly_requests,
        "monthly_error_budget_minutes": round(policy.monthly_error_budget_minutes, 2),
        "fast_burn_threshold": policy.fast_burn_threshold,
        "slow_burn_threshold": policy.slow_burn_threshold,
    }


if __name__ == "__main__":
    policy = build_policy("checkout-api", monthly_requests=100000)
    print(summarize_policy(policy))
    print(classify_burn_rate(15.0))
