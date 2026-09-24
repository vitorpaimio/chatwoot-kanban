"""Template Swarm com segredos montados, healthchecks e roteamento Traefik."""

from urllib.parse import urlsplit

from installer.config import Deployment

ENTRYPOINT = """#!/bin/sh
set -eu
export DATABASE_URL="$(cat /run/secrets/database_url)"
export ENCRYPTION_KEY="$(cat /run/secrets/encryption_key)"
exec "$@"
"""


MIGRATE = """import os, time, psycopg
end = time.monotonic() + 90
while True:
    try:
        connection = psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=3)
        with connection:
            connection.execute('SELECT 1')
        break
    except psycopg.OperationalError:
        if time.monotonic() >= end:
            raise SystemExit('Banco indisponível para migração')
        time.sleep(2)
os.execvp('alembic', ['alembic', 'upgrade', 'head'])
"""


def stack(config: Deployment, identity: str, image: str, running: bool = False) -> dict:
    """Renderiza documento sem valores secretos para docker stack deploy via stdin."""
    name = config.name
    owner = {"io.chatwoot-kanban.installation": identity}
    common = {
        "image": image,
        "entrypoint": ["/bin/sh", "/run/config/entrypoint.sh"],
        "environment": {
            "CHATWOOT_BASE_URL": config.chatwoot_url.rstrip("/"),
            "PUBLIC_URL": config.public_url.rstrip("/"),
            "WEBHOOK_BASE_URL": config.callback_url,
            "ENV": "production",
        },
        "secrets": [
            {"source": "database_url", "target": "database_url"},
            {"source": "encryption_key", "target": "encryption_key"},
        ],
        "configs": [{"source": "entrypoint", "target": "/run/config/entrypoint.sh"}],
        "networks": (
            ["private", "public"]
            if config.chatwoot_network == config.network
            else ["private", "chatwoot", "public"]
        ),
    }
    labels = {
        **owner,
        "traefik.enable": "true",
        f"traefik.http.routers.{name}.rule": (
            f"Host(`{urlsplit(config.public_url).hostname}`) && "
            "(Path(`/kanban`) || PathPrefix(`/kanban/`))"
        ),
        f"traefik.http.routers.{name}.priority": "200",
        f"traefik.http.routers.{name}.entrypoints": config.entrypoint,
        f"traefik.http.services.{name}.loadbalancer.server.port": "8000",
        "traefik.swarm.network": config.network,
    }
    if config.tls:
        labels[f"traefik.http.routers.{name}.tls"] = "true"
    return {
        "version": "3.8",
        "services": {
            "postgres": {
                "image": "postgres:16",
                "environment": {
                    "POSTGRES_DB": "kanban",
                    "POSTGRES_USER": "kanban",
                    "POSTGRES_PASSWORD_FILE": "/run/secrets/database_password",
                },
                "secrets": ["database_password"],
                "networks": ["private"],
                "volumes": ["data:/var/lib/postgresql/data"],
                "healthcheck": {
                    "test": ["CMD", "pg_isready", "-U", "kanban", "-d", "kanban"],
                    "interval": "5s",
                    "timeout": "3s",
                    "retries": 10,
                },
                "deploy": {
                    "replicas": 1,
                    "labels": owner,
                    "placement": {"constraints": ["node.role == manager"]},
                },
            },
            "migrate": {
                **common,
                "command": ["python", "-c", MIGRATE],
                "healthcheck": {"disable": True},
                "deploy": {
                    "replicas": 0,
                    "labels": owner,
                    "restart_policy": {"condition": "none"},
                },
            },
            "api": {
                **common,
                "command": [
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8000",
                    "--no-access-log",
                ],
                "deploy": {"replicas": int(running), "labels": labels},
            },
            "worker": {
                **common,
                "command": ["python", "-m", "app.worker"],
                "healthcheck": {
                    "test": [
                        "CMD",
                        "/bin/sh",
                        "/run/config/entrypoint.sh",
                        "python",
                        "-m",
                        "app.health",
                        "worker",
                    ],
                    "interval": "10s",
                    "timeout": "10s",
                    "start_period": "20s",
                    "retries": 3,
                },
                "deploy": {"replicas": int(running), "labels": owner},
            },
        },
        "networks": {
            "private": {"driver": "overlay"},
            "chatwoot": {"external": True, "name": config.chatwoot_network},
            "public": {"external": True, "name": config.network},
        },
        "volumes": {"data": {"labels": owner}},
        "configs": {"entrypoint": {"external": True, "name": name + "_entrypoint"}},
        "secrets": {
            key: {"external": True, "name": name + "_" + key}
            for key in ("database_password", "database_url", "encryption_key")
        },
    }
