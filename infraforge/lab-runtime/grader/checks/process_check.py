"""Process check — verifies a named process is (or is not) running inside
the container. Used for safety checks like "no rogue daemons left running."

grading.yaml usage:
  - id: no_debug_shell_open
    type: process
    layer: safety
    weight: 0.10
    description: "No stray root shells are running"
    process_name: "bash"
    expect_running: false
    run_as_user: "root"
"""
import docker
import docker.errors
from dataclasses import dataclass


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


class ProcessCheck:
    def __init__(self, spec: dict, container_ids: list[str]):
        self.spec = spec
        self.container_ids = container_ids
        self.client = docker.from_env()

    def run(self) -> CheckResult:
        check_id = self.spec["id"]
        layer = self.spec["layer"]
        description = self.spec["description"]
        weight = float(self.spec.get("weight", 0.05))
        process_name = self.spec["process_name"]
        expect_running = self.spec.get("expect_running", True)

        container = self._get_container(self.spec.get("container", "challenge"))
        if not container:
            return CheckResult(
                check_id=check_id, layer=layer, description=description,
                passed=False, weight=weight, detail="Container not found",
                points_earned=0, points_possible=weight * 100,
            )

        try:
            exit_code, output = container.exec_run(
                ["pgrep", "-x", process_name],
                user="root",
            )
            is_running = exit_code == 0
        except Exception as e:
            return CheckResult(
                check_id=check_id, layer=layer, description=description,
                passed=False, weight=weight, detail=f"pgrep failed: {e}",
                points_earned=0, points_possible=weight * 100,
            )

        passed = is_running == expect_running
        detail = (
            f"Process '{process_name}' is {'running' if is_running else 'not running'}"
            f" (expected: {'running' if expect_running else 'not running'})"
        )

        return CheckResult(
            check_id=check_id, layer=layer, description=description,
            passed=passed, weight=weight, detail=detail,
            points_earned=weight * 100 if passed else 0,
            points_possible=weight * 100,
        )

    def _get_container(self, role: str):
        for cid in self.container_ids:
            try:
                c = self.client.containers.get(cid)
                if role == "challenge" or role in c.name:
                    return c
            except docker.errors.NotFound:
                pass
        return None
