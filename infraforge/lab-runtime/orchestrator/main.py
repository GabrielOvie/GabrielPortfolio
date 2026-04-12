"""InfraForge Lab Orchestrator — internal API.

This service is NOT exposed to the internet.
It is only reachable by the platform API and worker via the platform-net.
All requests must carry X-API-Key.

Responsibilities:
  - Accept lab provisioning requests from the platform
  - Delegate to the LabProvisioner (Docker)
  - Track active runs in Redis
  - Forward grading requests to the grader service
  - Accept teardown requests
"""
import uuid
import os
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import structlog
import redis.asyncio as aioredis
import httpx
import json

from provisioner import LabProvisioner

log = structlog.get_logger()


class Settings(BaseSettings):
    orchestrator_api_key: str
    redis_url: str = "redis://redis:6379/0"
    grader_url: str = "http://lab-grader:9100"
    grader_api_key: str = ""
    max_concurrent_runs: int = 50
    default_run_timeout_minutes: int = 90

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
provisioner = LabProvisioner()
redis_client: aioredis.Redis = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    log.info("orchestrator_starting")
    yield
    await redis_client.close()
    log.info("orchestrator_stopped")


app = FastAPI(title="InfraForge Orchestrator", version="1.0.0", lifespan=lifespan)


# ── Auth ─────────────────────────────────────────────────────────────────────

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.orchestrator_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")


# ── Schemas ───────────────────────────────────────────────────────────────────

class ProvisionRequest(BaseModel):
    run_id: str
    template_id: str
    image_tag: str
    user_id: str
    timeout_minutes: int = 90


class GradeRequest(BaseModel):
    grading_spec: dict


class RunState(BaseModel):
    run_id: str
    orchestrator_run_id: str
    status: str
    created_at: str
    timeout_at: str
    container_ids: list[str]


# ── Redis helpers ─────────────────────────────────────────────────────────────

RUNS_KEY = "orchestrator:runs"


async def save_run_state(state: dict) -> None:
    await redis_client.hset(RUNS_KEY, state["orchestrator_run_id"], json.dumps(state))


async def load_run_state(orchestrator_run_id: str) -> dict | None:
    raw = await redis_client.hget(RUNS_KEY, orchestrator_run_id)
    return json.loads(raw) if raw else None


async def delete_run_state(orchestrator_run_id: str) -> None:
    await redis_client.hdel(RUNS_KEY, orchestrator_run_id)


async def count_active_runs() -> int:
    return await redis_client.hlen(RUNS_KEY)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}


@app.post("/runs", status_code=201, dependencies=[Depends(verify_api_key)])
async def provision_run(body: ProvisionRequest):
    active = await count_active_runs()
    if active >= settings.max_concurrent_runs:
        raise HTTPException(503, f"Orchestrator at capacity ({active}/{settings.max_concurrent_runs} runs)")

    run_id = uuid.UUID(body.run_id)
    timeout_at = datetime.utcnow() + timedelta(minutes=body.timeout_minutes)

    try:
        result = provisioner.provision(
            run_id=run_id,
            template_id=body.template_id,
            image_tag=body.image_tag,
            timeout_minutes=body.timeout_minutes,
        )
    except Exception as e:
        log.error("provision_failed", run_id=body.run_id, error=str(e))
        raise HTTPException(500, f"Provisioning failed: {e}")

    state = {
        "run_id": body.run_id,
        "orchestrator_run_id": result["orchestrator_run_id"],
        "status": "running",
        "created_at": datetime.utcnow().isoformat(),
        "timeout_at": timeout_at.isoformat(),
        "container_ids": result["container_ids"],
        "template_id": body.template_id,
    }
    await save_run_state(state)

    return {
        "orchestrator_run_id": result["orchestrator_run_id"],
        "credentials": result["credentials"],
        "status": "running",
    }


@app.get("/runs/{orchestrator_run_id}", dependencies=[Depends(verify_api_key)])
async def get_run(orchestrator_run_id: str):
    state = await load_run_state(orchestrator_run_id)
    if not state:
        raise HTTPException(404, "Run not found")
    # Also check actual container status
    container_status = provisioner.get_container_status(orchestrator_run_id)
    state["container_status"] = container_status
    return state


@app.post("/runs/{orchestrator_run_id}/grade", dependencies=[Depends(verify_api_key)])
async def trigger_grading(orchestrator_run_id: str, body: GradeRequest, background_tasks: BackgroundTasks):
    state = await load_run_state(orchestrator_run_id)
    if not state:
        raise HTTPException(404, "Run not found")

    grading_job_id = f"grade-{uuid.uuid4().hex[:16]}"

    # Forward to grader service async
    background_tasks.add_task(
        _call_grader,
        grading_job_id=grading_job_id,
        orchestrator_run_id=orchestrator_run_id,
        container_ids=state["container_ids"],
        grading_spec=body.grading_spec,
    )

    # Store pending grading job in Redis
    await redis_client.setex(
        f"grading:{grading_job_id}",
        300,  # 5 minute TTL
        json.dumps({"status": "pending", "orchestrator_run_id": orchestrator_run_id}),
    )

    return {"grading_job_id": grading_job_id}


@app.get("/grading/{grading_job_id}", dependencies=[Depends(verify_api_key)])
async def get_grading_result(grading_job_id: str):
    """Platform polls this to get the grading result."""
    raw = await redis_client.get(f"grading:{grading_job_id}")
    if not raw:
        raise HTTPException(404, "Grading job not found or expired")
    return json.loads(raw)


@app.delete("/runs/{orchestrator_run_id}", status_code=204, dependencies=[Depends(verify_api_key)])
async def teardown_run(orchestrator_run_id: str, background_tasks: BackgroundTasks):
    state = await load_run_state(orchestrator_run_id)
    # Teardown even if state is missing (idempotent)
    background_tasks.add_task(_do_teardown, orchestrator_run_id)
    if state:
        await delete_run_state(orchestrator_run_id)


async def _do_teardown(orchestrator_run_id: str):
    try:
        provisioner.teardown(orchestrator_run_id)
        log.info("teardown_complete", orchestrator_run_id=orchestrator_run_id)
    except Exception as e:
        log.error("teardown_failed", orchestrator_run_id=orchestrator_run_id, error=str(e))


async def _call_grader(
    grading_job_id: str,
    orchestrator_run_id: str,
    container_ids: list[str],
    grading_spec: dict,
):
    """Call the grader service and store result in Redis."""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.grader_url}/grade",
                headers={"X-API-Key": settings.grader_api_key},
                json={
                    "grading_job_id": grading_job_id,
                    "orchestrator_run_id": orchestrator_run_id,
                    "container_ids": container_ids,
                    "grading_spec": grading_spec,
                },
            )
            resp.raise_for_status()
            result = resp.json()

        await redis_client.setex(
            f"grading:{grading_job_id}",
            3600,
            json.dumps({"status": "completed", "result": result}),
        )
        log.info("grading_complete", grading_job_id=grading_job_id, score=result.get("final_score"))

    except Exception as e:
        log.error("grading_failed", grading_job_id=grading_job_id, error=str(e))
        await redis_client.setex(
            f"grading:{grading_job_id}",
            3600,
            json.dumps({"status": "failed", "error": str(e)}),
        )
