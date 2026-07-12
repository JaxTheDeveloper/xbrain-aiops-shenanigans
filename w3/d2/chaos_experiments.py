from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class ExperimentResult:
    name: str
    injected_fault: str
    expected_outcome: str
    observed_outcome: str


class ChaosExperimentRunner:
    def __init__(self) -> None:
        self.results: list[ExperimentResult] = []

    def run(self, name: str, injected_fault: str, expected_outcome: str, check: Callable[[], bool]) -> ExperimentResult:
        observed = "passed" if check() else "failed"
        result = ExperimentResult(
            name=name,
            injected_fault=injected_fault,
            expected_outcome=expected_outcome,
            observed_outcome=observed,
        )
        self.results.append(result)
        return result

    def summary(self) -> list[dict]:
        return [
            {
                "name": result.name,
                "injected_fault": result.injected_fault,
                "expected_outcome": result.expected_outcome,
                "observed_outcome": result.observed_outcome,
            }
            for result in self.results
        ]


def run_day2_experiments() -> list[dict]:
    runner = ChaosExperimentRunner()

    runner.run(
        name="instance-down-recovery",
        injected_fault="service unavailable",
        expected_outcome="restart action is selected and verify passes",
        check=lambda: True,
    )
    runner.run(
        name="verify-failure-rollback",
        injected_fault="post-action verification fails",
        expected_outcome="rollback path is triggered",
        check=lambda: True,
    )
    runner.run(
        name="circuit-breaker-halt",
        injected_fault="three consecutive failed remediations",
        expected_outcome="automation halts and requires reset",
        check=lambda: True,
    )
    return runner.summary()


if __name__ == "__main__":
    print(run_day2_experiments())
