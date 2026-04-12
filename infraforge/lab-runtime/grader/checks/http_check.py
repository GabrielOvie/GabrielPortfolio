"""HTTP endpoint check — verifies that an HTTP endpoint inside the lab
environment returns the expected status code and optionally body content.

grading.yaml usage:
  - id: api_healthy
    type: http
    layer: correctness
    weight: 0.15
    description: "Application returns HTTP 200 on /health"
    url: "http://{{container_ip}}:8080/health"
    method: GET
    expect_status: 200
    expect_body_contains: "ok"
    timeout_seconds: 10
"""
import httpx
from dataclasses import dataclass
from typing import Any
import docker
import docker.errors


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


class HttpCheck:
    def __init__(self, spec: dict, container_ids: list[str]):
        self.spec = spec
        self.container_ids = container_ids
        self.client = docker.from_env()

    def run(self) -> CheckResult:
        check_id = self.spec["id"]
        layer = self.spec["layer"]
        description = self.spec["description"]
        weight = float(self.spec.get("weight", 0.1))
        url_template = self.spec["url"]
        method = self.spec.get("method", "GET").upper()
        expect_status = self.spec.get("expect_status", 200)
        expect_body = self.spec.get("expect_body_contains")
        timeout = self.spec.get("timeout_seconds", 10)

        # Resolve {{container_ip}} placeholder
        container_ip = self._get_container_ip(self.spec.get("container", "challenge"))
        url = url_template.replace("{{container_ip}}", container_ip or "127.0.0.1")

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.request(method, url)
            status_code = resp.status_code
            body = resp.text[:1000]
        except Exception as e:
            return CheckResult(
                check_id=check_id, layer=layer, description=description,
                passed=False, weight=weight,
                detail=f"Request failed: {e}",
                points_earned=0, points_possible=weight * 100,
            )

        passed = True
        reasons = []

        if status_code != expect_status:
            passed = False
            reasons.append(f"status {status_code} (expected {expect_status})")

        if expect_body and expect_body not in body:
            passed = False
            reasons.append(f"body did not contain '{expect_body}'")

        detail = f"HTTP {status_code}"
        if reasons:
            detail = "; ".join(reasons)

        return CheckResult(
            check_id=check_id, layer=layer, description=description,
            passed=passed, weight=weight, detail=detail,
            points_earned=weight * 100 if passed else 0,
            points_possible=weight * 100,
        )

    def _get_container_ip(self, role: str) -> str | None:
        for cid in self.container_ids:
            try:
                c = self.client.containers.get(cid)
                if role == "challenge" or role in c.name:
                    networks = c.attrs.get("NetworkSettings", {}).get("Networks", {})
                    for net in networks.values():
                        ip = net.get("IPAddress")
                        if ip:
                            return ip
            except docker.errors.NotFound:
                pass
        return None
