"""Shell command check — runs a command inside the challenge container and
validates exit code and/or stdout against expected values.

grading.yaml usage:
  - id: service_active
    type: shell
    layer: correctness
    weight: 0.20
    description: "nginx.service is active and running"
    command: "systemctl is-active nginx"
    expect_exit_code: 0
    expect_stdout_contains: "active"
"""
import docker
import docker.errors
from dataclasses import dataclass
from typing import Any


@dataclass
class CheckResult:
    check_id: str
    layer: str
    description: str
    passed: bool
    weight: float
    detail: str
    points_earned: float
    points_possible: float


class ShellCheck:
    def __init__(self, spec: dict, container_ids: list[str]):
        self.spec = spec
        self.container_ids = container_ids
        self.client = docker.from_env()

    def run(self) -> CheckResult:
        check_id = self.spec["id"]
        layer = self.spec["layer"]
        description = self.spec["description"]
        weight = float(self.spec.get("weight", 0.1))
        command = self.spec["command"]
        expect_exit = self.spec.get("expect_exit_code", 0)
        expect_contains = self.spec.get("expect_stdout_contains")
        expect_not_contains = self.spec.get("expect_stdout_not_contains")
        target_container = self.spec.get("container", "challenge")

        container = self._get_container(target_container)
        if not container:
            return CheckResult(
                check_id=check_id,
                layer=layer,
                description=description,
                passed=False,
                weight=weight,
                detail="Target container not found",
                points_earned=0,
                points_possible=weight * 100,
            )

        try:
            exit_code, output = container.exec_run(
                cmd=["sh", "-c", command],
                user="root",
                demux=False,
            )
            stdout = output.decode("utf-8", errors="replace").strip() if output else ""
        except Exception as e:
            return CheckResult(
                check_id=check_id, layer=layer, description=description,
                passed=False, weight=weight,
                detail=f"exec failed: {e}",
                points_earned=0, points_possible=weight * 100,
            )

        # Evaluate
        passed = True
        reasons = []

        if exit_code != expect_exit:
            passed = False
            reasons.append(f"exit code {exit_code} (expected {expect_exit})")

        if expect_contains and expect_contains not in stdout:
            passed = False
            reasons.append(f"stdout did not contain '{expect_contains}'")

        if expect_not_contains and expect_not_contains in stdout:
            passed = False
            reasons.append(f"stdout contained disallowed string '{expect_not_contains}'")

        detail = stdout[:500]  # Truncate for storage
        if reasons:
            detail = "; ".join(reasons) + f"\nOutput: {stdout[:300]}"

        return CheckResult(
            check_id=check_id,
            layer=layer,
            description=description,
            passed=passed,
            weight=weight,
            detail=detail,
            points_earned=weight * 100 if passed else 0,
            points_possible=weight * 100,
        )

    def _get_container(self, role: str):
        """Find the container for this run by label."""
        for cid in self.container_ids:
            try:
                c = self.client.containers.get(cid)
                if role == "challenge" or role in c.name:
                    return c
            except docker.errors.NotFound:
                pass
        return None
