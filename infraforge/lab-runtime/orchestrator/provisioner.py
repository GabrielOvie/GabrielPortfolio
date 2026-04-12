"""Lab environment provisioner.

Spins up isolated Docker environments for a lab run.
Each run gets:
  - A dedicated Docker network (no cross-run visibility)
  - One or more containers from the lab image
  - Resource limits (CPU, memory)
  - Injected secrets (SSH credentials, scenario-specific env vars)
  - A port mapping for SSH access (exposed on the orchestrator host)

For VM-based labs (v2), this module would delegate to a libvirt/cloud API.
"""
import uuid
import secrets
import string
import socket
from typing import Any
import docker
import docker.errors
import structlog

log = structlog.get_logger()

# Resource defaults — containers share the worker host
DEFAULT_CPU_QUOTA = 50000   # 50% of one CPU core (docker: cpu_quota / cpu_period)
DEFAULT_CPU_PERIOD = 100000
DEFAULT_MEM_LIMIT = "512m"
DEFAULT_MEM_SWAP = "512m"   # Disable swap

# Port range for SSH exposure on the orchestrator host
SSH_PORT_START = 20000
SSH_PORT_END = 29999


def _find_free_port(start: int = SSH_PORT_START, end: int = SSH_PORT_END) -> int:
    """Find an available TCP port in the given range."""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free ports available in SSH range")


def _generate_ssh_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class LabProvisioner:
    def __init__(self):
        self.client = docker.from_env()

    def provision(
        self,
        run_id: uuid.UUID,
        template_id: str,
        image_tag: str,
        timeout_minutes: int,
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Provision an isolated environment for one lab run.

        Returns a dict with:
          - orchestrator_run_id: str (the Docker network/container prefix)
          - credentials: dict (ssh_host, ssh_port, ssh_user, ssh_password)
          - container_ids: list[str]
        """
        run_prefix = f"if-run-{str(run_id)[:8]}"
        ssh_password = _generate_ssh_password()
        ssh_port = _find_free_port()

        log.info("provisioning_lab", run_id=str(run_id), template_id=template_id, image_tag=image_tag)

        # 1. Create isolated network
        network = self._create_network(run_prefix)

        try:
            # 2. Launch the challenge container
            container = self._launch_container(
                name=f"{run_prefix}-challenge",
                image=image_tag,
                network=network.name,
                ssh_port=ssh_port,
                ssh_password=ssh_password,
                timeout_minutes=timeout_minutes,
                extra_env=extra_env or {},
            )

            log.info(
                "lab_provisioned",
                run_id=str(run_id),
                container_id=container.id[:12],
                ssh_port=ssh_port,
            )

            return {
                "orchestrator_run_id": run_prefix,
                "credentials": {
                    "ssh_host": _get_host_ip(),
                    "ssh_port": ssh_port,
                    "ssh_user": "user",
                    "ssh_password": ssh_password,
                },
                "container_ids": [container.id],
            }

        except Exception as e:
            log.error("provision_failed", run_id=str(run_id), error=str(e))
            # Best-effort cleanup
            self._teardown_by_prefix(run_prefix)
            raise

    def _create_network(self, prefix: str) -> docker.models.networks.Network:
        """Create an isolated bridge network for this run."""
        return self.client.networks.create(
            name=f"{prefix}-net",
            driver="bridge",
            internal=False,  # containers need internet for package installs in some labs
            options={
                "com.docker.network.bridge.enable_icc": "false",  # no inter-container talk across runs
            },
            labels={
                "infraforge.managed": "true",
                "infraforge.prefix": prefix,
            },
        )

    def _launch_container(
        self,
        name: str,
        image: str,
        network: str,
        ssh_port: int,
        ssh_password: str,
        timeout_minutes: int,
        extra_env: dict[str, str],
    ) -> docker.models.containers.Container:
        env = {
            "LAB_SSH_PASSWORD": ssh_password,
            "LAB_TIMEOUT_MINUTES": str(timeout_minutes),
            **extra_env,
        }

        return self.client.containers.run(
            image=image,
            name=name,
            detach=True,
            network=network,
            ports={"22/tcp": ssh_port},
            environment=env,
            # Resource limits
            cpu_quota=DEFAULT_CPU_QUOTA,
            cpu_period=DEFAULT_CPU_PERIOD,
            mem_limit=DEFAULT_MEM_LIMIT,
            memswap_limit=DEFAULT_MEM_SWAP,
            # Security
            cap_drop=["ALL"],
            cap_add=["CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID", "NET_BIND_SERVICE"],
            security_opt=["no-new-privileges:true"],
            read_only=False,  # Labs need writable FS
            # Housekeeping
            labels={
                "infraforge.managed": "true",
                "infraforge.prefix": name.rsplit("-", 1)[0],
                "infraforge.role": "challenge",
            },
            restart_policy={"Name": "no"},
        )

    def teardown(self, orchestrator_run_id: str) -> None:
        """Remove all containers and network for a run."""
        log.info("tearing_down_run", orchestrator_run_id=orchestrator_run_id)
        self._teardown_by_prefix(orchestrator_run_id)

    def _teardown_by_prefix(self, prefix: str) -> None:
        """Kill and remove all Docker objects tagged with this run prefix."""
        # Containers
        containers = self.client.containers.list(
            all=True,
            filters={"label": f"infraforge.prefix={prefix}"},
        )
        for container in containers:
            try:
                container.stop(timeout=5)
                container.remove(force=True)
                log.info("container_removed", container_id=container.id[:12])
            except docker.errors.NotFound:
                pass

        # Networks
        networks = self.client.networks.list(
            filters={"label": f"infraforge.prefix={prefix}"},
        )
        for network in networks:
            try:
                network.remove()
                log.info("network_removed", network_name=network.name)
            except docker.errors.NotFound:
                pass

    def get_container_status(self, orchestrator_run_id: str) -> dict[str, Any]:
        containers = self.client.containers.list(
            filters={"label": f"infraforge.prefix={orchestrator_run_id}"},
        )
        if not containers:
            return {"status": "not_found", "containers": []}
        return {
            "status": "running" if all(c.status == "running" for c in containers) else "degraded",
            "containers": [
                {"id": c.id[:12], "name": c.name, "status": c.status}
                for c in containers
            ],
        }


def _get_host_ip() -> str:
    """Get the host IP accessible from outside the container."""
    # In production this would be the public IP / load balancer hostname.
    # For local dev, resolve the docker bridge IP.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()
