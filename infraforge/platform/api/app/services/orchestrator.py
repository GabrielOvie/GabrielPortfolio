"""Client for the lab orchestrator service.

The platform API never talks to Docker directly.
All lab lifecycle calls go through the orchestrator API,
which lives in the lab-runtime plane.
"""
import uuid
from typing import Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

settings = get_settings()


class OrchestratorError(Exception):
    pass


class OrchestratorClient:
    def __init__(self):
        self.base_url = settings.orchestrator_url
        self.api_key = settings.orchestrator_api_key

    def _headers(self) -> dict:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def provision_lab(
        self,
        run_id: uuid.UUID,
        template_id: str,
        image_tag: str,
        user_id: uuid.UUID,
        timeout_minutes: int,
    ) -> dict[str, Any]:
        """Tell the orchestrator to spin up an isolated lab environment.

        Returns access credentials: ssh_host, ssh_port, ssh_user, ssh_password.
        """
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/runs",
                headers=self._headers(),
                json={
                    "run_id": str(run_id),
                    "template_id": template_id,
                    "image_tag": image_tag,
                    "user_id": str(user_id),
                    "timeout_minutes": timeout_minutes,
                },
            )
        if resp.status_code != 201:
            raise OrchestratorError(f"Orchestrator returned {resp.status_code}: {resp.text}")
        return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def teardown_run(self, orchestrator_run_id: str) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                f"{self.base_url}/runs/{orchestrator_run_id}",
                headers=self._headers(),
            )
        if resp.status_code not in (200, 204, 404):
            raise OrchestratorError(f"Teardown failed: {resp.status_code}: {resp.text}")

    async def get_run_status(self, orchestrator_run_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.base_url}/runs/{orchestrator_run_id}",
                headers=self._headers(),
            )
        if resp.status_code == 404:
            return {"status": "not_found"}
        resp.raise_for_status()
        return resp.json()

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=8))
    async def trigger_grading(self, orchestrator_run_id: str, grading_spec: dict) -> str:
        """Ask the grader to evaluate the current environment state.
        Returns a grading job ID.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/runs/{orchestrator_run_id}/grade",
                headers=self._headers(),
                json={"grading_spec": grading_spec},
            )
        resp.raise_for_status()
        return resp.json()["grading_job_id"]


def get_orchestrator_client() -> OrchestratorClient:
    return OrchestratorClient()
