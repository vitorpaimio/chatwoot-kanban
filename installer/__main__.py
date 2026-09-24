"""Entrada do planejamento: python -m installer install --dry-run."""

import argparse
import json
import sys
from pathlib import Path

from cryptography.fernet import InvalidToken
from pydantic import ValidationError

from app.provisioning.attributes import attribute_plan
from installer.compose import ComposeLifecycle
from installer.config import Deployment
from installer.lifecycle import Lifecycle
from installer.swarm import InspectionError, inspect


def installation_plan(inventory: dict, confirmed_network: str | None) -> dict:
    """Gera plano mínimo sem copiar conteúdo remoto ou conceder propriedade."""
    accounts = []
    blocked = confirmed_network != inventory["network"]
    for account, definitions in sorted(
        inventory["accounts"].items(), key=lambda x: int(x[0])
    ):
        attributes = []
        for item in attribute_plan(definitions, {}):
            status = item["status"]
            blocked = blocked or status == "conflict"
            attributes.append({"key": item["key"], "action": status})
        accounts.append({"account_id": int(account), "attributes": attributes})
    return {
        "schema_version": 1,
        "operation": "install",
        "dry_run": True,
        "network": inventory["network"],
        "network_confirmed": confirmed_network == inventory["network"],
        "blocked": blocked,
        "accounts": accounts,
        "execution_available": False,
    }


def main() -> int:
    """Inspeciona e imprime plano; código 2 indica bloqueio ou inspeção incompleta."""
    parser = argparse.ArgumentParser(
        description="Instalador Swarm/Traefik e Compose/Nginx do Kanban"
    )
    parser.add_argument(
        "operation", choices=["install", "update", "uninstall", "status", "restore"]
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--account", type=int, action="append")
    parser.add_argument("--network", default="network_public")
    parser.add_argument("--confirm-network")
    parser.add_argument("--chatwoot-container")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--purge-attributes", action="store_true")
    parser.add_argument("--confirm-attribute-data-loss", action="store_true")
    parser.add_argument("--backup")
    args = parser.parse_args()
    if args.config:
        return configured(args)
    if not args.dry_run or not args.account or not args.chatwoot_container:
        parser.error("Use --config; formato legado suporta apenas install --dry-run.")
    try:
        inventory = inspect(args.network, args.chatwoot_container, args.account)
        plan = installation_plan(inventory, args.confirm_network)
    except InspectionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (ValueError, KeyError, TypeError, AttributeError):
        print(
            "Não foi possível concluir o plano; verifique Swarm, rede e contas.",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 2 if plan["blocked"] else 0


def configured(args: argparse.Namespace) -> int:
    """Executa operação configurada e registra falha sem ecoar credenciais."""
    lifecycle = None
    try:
        config = Deployment.model_validate_json(args.config.read_text())
        lifecycle_class = ComposeLifecycle if config.adapter == "compose" else Lifecycle
        lifecycle = lifecycle_class(
            config, args.state_dir or Path(".local/installations") / config.name
        )
        if args.dry_run:
            result = lifecycle.plan(
                args.operation, args.confirm_network, args.purge_attributes
            )
        elif args.operation == "status":
            lifecycle.preflight()
            result = lifecycle.status()
        else:
            lifecycle.state.lock()
            if args.operation in ("install", "update"):
                result = lifecycle.install(args.operation, args.confirm_network)
            elif args.operation == "uninstall":
                result = lifecycle.uninstall(
                    args.confirm_network,
                    args.purge_attributes,
                    args.confirm_attribute_data_loss,
                )
            else:
                if not args.backup:
                    raise InspectionError("Selecione --backup para restaurar.")
                result = lifecycle.restore(args.backup, args.confirm_network)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("blocked") or result.get("healthy") is False else 0
    except (
        InspectionError,
        OSError,
        ValueError,
        KeyError,
        ValidationError,
        InvalidToken,
    ) as exc:
        if (
            lifecycle
            and hasattr(lifecycle.state, "_lock")
            and lifecycle.state.data.get("status")
            in ("backing_up", "installing", "updating", "uninstalling", "restoring")
        ):
            lifecycle.state.save(status="failed")
        if isinstance(exc, InspectionError):
            print(str(exc), file=sys.stderr)
        print(
            "Operação incompleta; confira configuração, serviços e manifesto. "
            "Saídas remotas foram omitidas para proteger credenciais.",
            file=sys.stderr,
        )
        return 2
    finally:
        if lifecycle:
            lifecycle.state.close()


if __name__ == "__main__":
    raise SystemExit(main())
