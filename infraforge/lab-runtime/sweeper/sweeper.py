"""Lab run sweeper — kills stale containers and orphaned Docker resources.

Runs every SWEEP_INTERVAL_SECONDS (default: 60s).
Catches anything the orchestrator missed: crashed containers, network leaks,
runs that timed out without the platform worker noticing.
"""
import asyncio
import os
import json
from datetime import datetime
import docker
import docker.errors
import httpx
import structlog

log = structlog.get_logger()

SWEEP_INTERVAL = int(os.environ.get("SWEEP_INTERVAL_SECONDS", "60"))
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://lab-orchestrator:9000")
ORCHESTRATOR_API_KEY = os.environ.get("ORCHESTRATOR_API_KEY", "")
MANAGED_LABEL = "infraforge.managed"


async def sweep_once(client: docker.DockerClient):
    """One sweep pass."""
    log.info("sweep_start")
    swept_containers = 0
    swept_networks = 0

    # ── Find all managed containers ───────────────────────────────────────────
    containers = client.containers.list(
        all=True,
        filters={"label": f"{MANAGED_LABEL}=true"},
    )

    for container in containers:
        labels = container.labels
        prefix = labels.get("infraforge.prefix", "")
        if not prefix:
            continue

        # Check if this run is still registered with the orchestrator
        is_known = await _check_run_known(prefix)

        # Container is in a terminal state and not tracked = orphan
        if container.status in ("exited", "dead") or not is_known:
            try:
                container.stop(timeout=3)
            except Exception:
                pass
            try:
                container.remove(force=True)
                swept_containers += 1
                log.info("swept_container", container=container.name, status=container.status, known=is_known)
            except docker.errors.NotFound:
                pass

    # ── Sweep orphaned networks ───────────────────────────────────────────────
    networks = client.networks.list(
        filters={"label": f"{MANAGED_LABEL}=true"},
    )

    for network in networks:
        prefix = network.labels.get("infraforge.prefix", "")
        if not prefix:
            continue
        # A network is orphaned if no managed containers reference it
        network.reload()
        if not network.containers:
            try:
                network.remove()
                swept_networks += 1
                log.info("swept_network", network=network.name)
            except docker.errors.NotFound:
                pass

    log.info("sweep_complete", containers=swept_containers, networks=swept_networks)


async def _check_run_known(orchestrator_run_id: str) -> bool:
    """Ask the orchestrator if it knows about this run."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{ORCHESTRATOR_URL}/runs/{orchestrator_run_id}",
                headers={"X-API-Key": ORCHESTRATOR_API_KEY},
            )
            return resp.status_code == 200
    except Exception:
        # If orchestrator is unreachable, assume run is known (don't delete prematurely)
        return True


async def main():
    client = docker.from_env()
    log.info("sweeper_starting", interval_seconds=SWEEP_INTERVAL)

    while True:
        try:
            await sweep_once(client)
        except Exception as e:
            log.error("sweep_error", error=str(e))
        await asyncio.sleep(SWEEP_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
