"""File and permission check — validates file existence, content, ownership,
and permissions inside the container.

grading.yaml usage:
  # Existence + content
  - id: config_restored
    type: file
    layer: correctness
    weight: 0.10
    description: "/etc/nginx/nginx.conf exists and contains 'server_name'"
    path: "/etc/nginx/nginx.conf"
    expect_exists: true
    expect_contains: "server_name"

  # Permission check
  - id: shadow_permissions
    type: file
    layer: safety
    weight: 0.10
    description: "/etc/shadow permissions are 640 or stricter"
    path: "/etc/shadow"
    expect_permissions_max: "640"

  # No world-writable files
  - id: no_world_writable
    type: file
    layer: safety
    weight: 0.10
    description: "/etc is not world-writable"
    path: "/etc"
    expect_world_writable: false
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


class FileCheck:
    def __init__(self, spec: dict, container_ids: list[str]):
        self.spec = spec
        self.container_ids = container_ids
        self.client = docker.from_env()

    def run(self) -> CheckResult:
        check_id = self.spec["id"]
        layer = self.spec["layer"]
        description = self.spec["description"]
        weight = float(self.spec.get("weight", 0.10))
        path = self.spec["path"]

        container = self._get_container(self.spec.get("container", "challenge"))
        if not container:
            return CheckResult(
                check_id=check_id, layer=layer, description=description,
                passed=False, weight=weight, detail="Container not found",
                points_earned=0, points_possible=weight * 100,
            )

        passed = True
        reasons = []

        # Existence check
        expect_exists = self.spec.get("expect_exists")
        if expect_exists is not None:
            exists = self._file_exists(container, path)
            if exists != expect_exists:
                passed = False
                reasons.append(f"{path} {'does not exist' if expect_exists else 'should not exist'}")

        # Content check
        expect_contains = self.spec.get("expect_contains")
        if expect_contains and passed:
            content = self._read_file(container, path)
            if content is None or expect_contains not in content:
                passed = False
                reasons.append(f"{path} does not contain '{expect_contains}'")

        # Permission check (octal string like "640")
        expect_perm_max = self.spec.get("expect_permissions_max")
        if expect_perm_max:
            actual_perm = self._get_permissions(container, path)
            if actual_perm and int(actual_perm, 8) > int(expect_perm_max, 8):
                passed = False
                reasons.append(f"{path} permissions {actual_perm} exceed max {expect_perm_max}")

        # World-writable check
        expect_world_writable = self.spec.get("expect_world_writable")
        if expect_world_writable is not None:
            is_ww = self._is_world_writable(container, path)
            if is_ww != expect_world_writable:
                passed = False
                reasons.append(f"{path} {'is not' if expect_world_writable else 'is'} world-writable")

        detail = "; ".join(reasons) if reasons else f"All checks passed for {path}"
        return CheckResult(
            check_id=check_id, layer=layer, description=description,
            passed=passed, weight=weight, detail=detail,
            points_earned=weight * 100 if passed else 0,
            points_possible=weight * 100,
        )

    def _exec(self, container, cmd: list[str]) -> tuple[int, str]:
        exit_code, output = container.exec_run(cmd, user="root")
        return exit_code, (output.decode("utf-8", errors="replace").strip() if output else "")

    def _file_exists(self, container, path: str) -> bool:
        exit_code, _ = self._exec(container, ["test", "-e", path])
        return exit_code == 0

    def _read_file(self, container, path: str) -> str | None:
        exit_code, content = self._exec(container, ["cat", path])
        return content if exit_code == 0 else None

    def _get_permissions(self, container, path: str) -> str | None:
        exit_code, out = self._exec(container, ["stat", "-c", "%a", path])
        return out if exit_code == 0 else None

    def _is_world_writable(self, container, path: str) -> bool:
        exit_code, out = self._exec(container, ["find", path, "-maxdepth", "0", "-perm", "-o+w"])
        return exit_code == 0 and bool(out)

    def _get_container(self, role: str):
        for cid in self.container_ids:
            try:
                c = self.client.containers.get(cid)
                if role == "challenge" or role in c.name:
                    return c
            except docker.errors.NotFound:
                pass
        return None
