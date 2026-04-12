"""InfraForge Grader — internal API.

Receives grading requests from the orchestrator, runs the GradingEngine,
and returns structured results.
"""
import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import structlog
import docker

from grader.engine import GradingEngine

log = structlog.get_logger()


class Settings(BaseSettings):
    grader_api_key: str = ""
    redis_url: str = "redis://redis:6379/0"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("grader_starting")
    yield
    log.info("grader_stopped")


app = FastAPI(title="InfraForge Grader", version="1.0.0", lifespan=lifespan)


def verify_api_key(x_api_key: str = Header(...)):
    if settings.grader_api_key and x_api_key != settings.grader_api_key:
        raise HTTPException(403, "Invalid API key")


class GradeRequest(BaseModel):
    grading_job_id: str
    orchestrator_run_id: str
    container_ids: list[str]
    grading_spec: dict
    duration_seconds: int | None = None


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}


@app.post("/grade", dependencies=[Depends(verify_api_key)])
async def grade(body: GradeRequest):
    """Run all grading checks and return structured results."""
    log.info(
        "grading_request",
        job_id=body.grading_job_id,
        run_id=body.orchestrator_run_id,
        containers=body.container_ids,
    )

    engine = GradingEngine(
        grading_spec=body.grading_spec,
        container_ids=body.container_ids,
        duration_seconds=body.duration_seconds,
    )

    try:
        result = engine.run()
    except Exception as e:
        log.error("grading_engine_error", job_id=body.grading_job_id, error=str(e))
        raise HTTPException(500, f"Grading engine error: {e}")

    return {
        "grading_job_id": body.grading_job_id,
        "orchestrator_run_id": body.orchestrator_run_id,
        "correctness_score": result.correctness_score,
        "safety_score": result.safety_score,
        "efficiency_score": result.efficiency_score,
        "final_score": result.final_score,
        "passed": result.passed,
        "summary": result.summary,
        "check_results": result.check_results,
    }
