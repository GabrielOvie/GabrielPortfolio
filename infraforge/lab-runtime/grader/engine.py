"""Grading engine — orchestrates all checks for a lab run.

Three-layer scoring model:
  Layer 1 — Correctness (60%): Did the system reach goal state?
  Layer 2 — Safety      (25%): Did the user avoid reckless actions?
  Layer 3 — Efficiency  (15%): How fast and how cleanly?

Each check in grading.yaml contributes to one layer.
Within a layer, checks are weighted proportionally (weights must sum to 1.0
per layer, or they are normalized automatically).

Scoring formula:
  layer_score = sum(check.passed * check.weight) / sum(check.weight) * 100
  final_score = correctness_score * 0.60 + safety_score * 0.25 + efficiency_score * 0.15

A run passes if final_score >= 60.
"""
from __future__ import annotations
import time
import structlog
from dataclasses import dataclass, asdict

from grader.checks import CHECK_REGISTRY

log = structlog.get_logger()

PASS_THRESHOLD = 60.0
LAYER_WEIGHTS = {
    "correctness": 0.60,
    "safety": 0.25,
    "efficiency": 0.15,
}


@dataclass
class GradingResult:
    correctness_score: float
    safety_score: float
    efficiency_score: float
    final_score: float
    passed: bool
    summary: str
    check_results: list[dict]


class GradingEngine:
    def __init__(self, grading_spec: dict, container_ids: list[str], duration_seconds: int | None = None):
        self.spec = grading_spec
        self.container_ids = container_ids
        self.duration_seconds = duration_seconds

    def run(self) -> GradingResult:
        checks = self.spec.get("checks", [])
        if not checks:
            log.warning("no_checks_defined")
            return self._empty_result("No checks defined in grading spec")

        log.info("grading_started", check_count=len(checks))
        t0 = time.time()

        # Execute all checks
        check_results = []
        for check_spec in checks:
            check_type = check_spec.get("type")
            check_cls = CHECK_REGISTRY.get(check_type)
            if not check_cls:
                log.warning("unknown_check_type", type=check_type)
                continue

            try:
                checker = check_cls(spec=check_spec, container_ids=self.container_ids)
                result = checker.run()
                check_results.append(result)
                log.info(
                    "check_complete",
                    check_id=result.check_id,
                    layer=result.layer,
                    passed=result.passed,
                    points=f"{result.points_earned:.0f}/{result.points_possible:.0f}",
                )
            except Exception as e:
                log.error("check_error", check_id=check_spec.get("id"), error=str(e))
                # Failed check = not passed
                from grader.checks.shell_check import CheckResult
                check_results.append(CheckResult(
                    check_id=check_spec.get("id", "unknown"),
                    layer=check_spec.get("layer", "correctness"),
                    description=check_spec.get("description", ""),
                    passed=False,
                    weight=float(check_spec.get("weight", 0.1)),
                    detail=f"Check execution error: {e}",
                    points_earned=0,
                    points_possible=float(check_spec.get("weight", 0.1)) * 100,
                ))

        elapsed = time.time() - t0

        # Compute layer scores
        layer_scores = self._compute_layer_scores(check_results)

        # Apply efficiency boost/penalty based on timing
        # Use the spec's time_par_minutes if defined
        efficiency_score = self._compute_efficiency(
            layer_scores.get("efficiency", 100.0),
            check_results,
        )

        correctness = layer_scores.get("correctness", 0.0)
        safety = layer_scores.get("safety", 100.0)

        final_score = (
            correctness * LAYER_WEIGHTS["correctness"] +
            safety * LAYER_WEIGHTS["safety"] +
            efficiency_score * LAYER_WEIGHTS["efficiency"]
        )
        final_score = round(min(100.0, max(0.0, final_score)), 2)
        passed = final_score >= PASS_THRESHOLD

        summary = self._generate_summary(check_results, correctness, safety, efficiency_score, final_score, passed)

        log.info(
            "grading_complete",
            correctness=correctness,
            safety=safety,
            efficiency=efficiency_score,
            final_score=final_score,
            passed=passed,
            elapsed_seconds=round(elapsed, 2),
        )

        return GradingResult(
            correctness_score=round(correctness, 2),
            safety_score=round(safety, 2),
            efficiency_score=round(efficiency_score, 2),
            final_score=final_score,
            passed=passed,
            summary=summary,
            check_results=[self._check_to_dict(r) for r in check_results],
        )

    def _compute_layer_scores(self, results: list) -> dict[str, float]:
        """For each layer, compute weighted score 0–100."""
        layers: dict[str, list] = {"correctness": [], "safety": [], "efficiency": []}

        for r in results:
            layer = r.layer if r.layer in layers else "correctness"
            layers[layer].append(r)

        scores = {}
        for layer, layer_results in layers.items():
            if not layer_results:
                scores[layer] = 100.0  # No checks = full score (vacuously true)
                continue
            total_weight = sum(r.weight for r in layer_results)
            if total_weight == 0:
                scores[layer] = 0.0
                continue
            earned = sum(r.weight for r in layer_results if r.passed)
            scores[layer] = (earned / total_weight) * 100.0

        return scores

    def _compute_efficiency(self, base_efficiency: float, results: list) -> float:
        """Apply timing bonus/penalty on top of explicit efficiency checks.

        If the spec defines time_par_minutes, beating par gives a bonus,
        going over penalizes. The range is ±10 points on the efficiency score.
        """
        par_minutes = self.spec.get("time_par_minutes")
        if not par_minutes or not self.duration_seconds:
            return base_efficiency

        actual_minutes = self.duration_seconds / 60
        ratio = actual_minutes / par_minutes  # <1 = under par, >1 = over par

        if ratio <= 0.5:
            bonus = 10.0   # Blazing fast
        elif ratio <= 1.0:
            bonus = (1.0 - ratio) * 20  # Linear bonus for beating par
        elif ratio <= 2.0:
            bonus = -(ratio - 1.0) * 10  # Linear penalty for going over
        else:
            bonus = -10.0  # Way over par

        return min(100.0, max(0.0, base_efficiency + bonus))

    def _generate_summary(
        self,
        results: list,
        correctness: float,
        safety: float,
        efficiency: float,
        final_score: float,
        passed: bool,
    ) -> str:
        """Generate a human-readable summary for portfolio cards."""
        total_checks = len(results)
        passed_checks = sum(1 for r in results if r.passed)

        # Safety failures are highlighted
        safety_failures = [r for r in results if r.layer == "safety" and not r.passed]

        mins = (self.duration_seconds // 60) if self.duration_seconds else None
        time_str = f" in {mins} min" if mins else ""

        if passed:
            base = f"Completed{time_str}. Passed {passed_checks}/{total_checks} checks."
        else:
            base = f"Did not pass (score {final_score:.0f}/100). Passed {passed_checks}/{total_checks} checks."

        if safety_failures:
            sf = ", ".join(r.description for r in safety_failures[:3])
            base += f" Safety issues: {sf}."

        return base

    @staticmethod
    def _check_to_dict(result) -> dict:
        return {
            "check_id": result.check_id,
            "layer": result.layer,
            "description": result.description,
            "passed": result.passed,
            "weight": result.weight,
            "detail": result.detail,
            "points_earned": result.points_earned,
            "points_possible": result.points_possible,
        }

    def _empty_result(self, reason: str) -> GradingResult:
        return GradingResult(
            correctness_score=0.0,
            safety_score=0.0,
            efficiency_score=0.0,
            final_score=0.0,
            passed=False,
            summary=reason,
            check_results=[],
        )
