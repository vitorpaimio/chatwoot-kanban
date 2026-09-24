"""Instalação guiada na VPS, reutilizando o ciclo de vida e seus recibos."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import ValidationError

from installer import terminal
from installer.compose import ComposeLifecycle
from installer.config import Deployment
from installer.lifecycle import Lifecycle
from installer.routing import proxy_network
from installer.state import State, write_private
from installer.swarm import InspectionError

ROOT = Path("/opt/chatwoot-kanban")
INVENTORY = """require 'json'
ActiveRecord::Base.transaction do
  ActiveRecord::Base.connection.execute('SET TRANSACTION READ ONLY')
  db = ActiveRecord::Base.connection_db_config.configuration_hash
  puts 'KANBAN_DISCOVERY=' + JSON.generate({
    accounts: Account.order(:id).pluck(:id, :name),
    url: ENV['FRONTEND_URL'],
    force_ssl: Rails.application.config.force_ssl ? true : false,
    database: db.slice(:host, :database, :username)
  })
end
"""


def docker(*args: str, data: str | None = None) -> str:
    """Usa somente o daemon local e não ecoa respostas com dados sensíveis."""
    try:
        return subprocess.run(
            ["docker", "--context", "default", *args],
            input=data,
            text=True,
            capture_output=True,
            check=True,
            timeout=300,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        raise InspectionError(
            f"Falha ao executar Docker ({args[0]}); saída remota omitida."
        ) from None


def inspect(kind: str, name: str) -> dict:
    """Lê um recurso Docker sem persistir ambiente ou credenciais."""
    return json.loads(docker(kind, "inspect", name))[0]


def choose(title: str, values: list, label, automatic: bool):
    """Escolhe o único candidato; ambiguidades exigem seleção explícita."""
    if not values:
        raise InspectionError(f"{title}: nenhum candidato compatível encontrado.")
    if len(values) == 1:
        return values[0]
    if automatic or not terminal.interactive():
        raise InspectionError(f"{title}: há várias opções; execute interativamente.")
    index = terminal.select(title, [str(label(value)) for value in values])[0]
    return values[index]


def service_name(container: dict, adapter: str) -> str | None:
    """Obtém identidade do orquestrador; nunca adota containers avulsos."""
    labels = container["Config"].get("Labels") or {}
    key = (
        "com.docker.swarm.service.name"
        if adapter == "swarm"
        else "com.docker.compose.service"
    )
    return labels.get(key)


def service_aliases(container: dict) -> dict[str, list[str]]:
    """Aliases declarados no serviço Swarm, por ID de rede.

    O daemon nem sempre os repete no inspect do container; sem eles, um banco
    acessado por alias de rede (ex.: ``pgvector``) não seria encontrado.
    """
    name = service_name(container, "swarm")
    if not name:
        return {}
    networks = inspect("service", name).get("Spec", {}).get("TaskTemplate", {})
    return {
        net["Target"]: net.get("Aliases") or []
        for net in networks.get("Networks") or []
        if net.get("Target")
    }


def discover(args: argparse.Namespace, image: str) -> Deployment:
    """Detecta Rails, banco, redes e contas sem gravar no Chatwoot."""
    containers = [inspect("container", cid) for cid in docker("ps", "-q").split()]
    candidates = []
    for item in containers:
        config = item["Config"]
        command = " ".join(config.get("Cmd") or [])
        if (
            "rails" in command
            and re.search(r"\b(server|s)\b", command)
            and (service_name(item, "swarm") or service_name(item, "compose"))
        ):
            candidates.append(item)
    if args.container:
        candidates = [
            c for c in candidates if args.container in (c["Id"], c["Name"].lstrip("/"))
        ]
    rails = choose("Instalação Chatwoot", candidates, lambda c: c["Name"], args.yes)
    adapter = "swarm" if service_name(rails, "swarm") else "compose"
    wrapper = args.rails_wrapper or []
    # Não executar strings livres como comandos nem interpretar shell.
    if len(wrapper) > 4 or any(
        not re.fullmatch(r"[a-zA-Z0-9_./-]+", w) for w in wrapper
    ):
        raise InspectionError("Wrapper inválido.")

    def inventory_output():
        return docker(
            "exec",
            "-i",
            rails["Id"],
            *wrapper,
            "bundle",
            "exec",
            "rails",
            "runner",
            "-",
            data=INVENTORY,
        )

    try:
        response = inventory_output()
    except InspectionError:
        # Instalações com Docker secrets carregam variáveis no entrypoint existente.
        observed = rails["Config"].get("Entrypoint") or []
        if (
            wrapper
            or not observed
            or len(observed) > 4
            or any(not re.fullmatch(r"[a-zA-Z0-9_./-]+", part) for part in observed)
        ):
            raise
        wrapper = observed
        response = inventory_output()
    lines = [
        line.removeprefix("KANBAN_DISCOVERY=")
        for line in response.splitlines()
        if line.startswith("KANBAN_DISCOVERY=")
    ]
    if len(lines) != 1:
        raise InspectionError("Rails não retornou inventário único.")
    inventory = json.loads(lines[0])
    available = inventory["accounts"]
    if not available:
        raise InspectionError("Crie uma conta no Chatwoot antes de instalar o Kanban.")
    if args.accounts:
        accounts = sorted(set(args.accounts))
        if not set(accounts) <= {row[0] for row in available}:
            raise InspectionError("Conta solicitada não existe nesta instalação.")
    elif args.all_accounts:
        accounts = sorted({row[0] for row in available})
    elif terminal.interactive() and not args.yes:
        indexes = terminal.select(
            "Em quais contas você quer ativar o Kanban?",
            [f"{name} (#{account})" for account, name in available],
            multiple=True,
        )
        accounts = sorted(available[index][0] for index in indexes)
    else:
        accounts = [choose("Conta Chatwoot", available, lambda row: row, args.yes)[0]]
    args.account_names = {account: name for account, name in available}
    db = inventory["database"]
    rails_nets = rails["NetworkSettings"]["Networks"]
    db_candidates = []
    for item in containers:
        if not service_name(item, adapter):
            continue
        for name, net in item["NetworkSettings"]["Networks"].items():
            if name not in rails_nets:
                continue
            aliases = [
                *(net.get("Aliases") or []),
                *(net.get("DNSNames") or []),
                net.get("IPAddress"),
                service_name(item, adapter),
            ]
            if adapter == "swarm" and net.get("NetworkID"):
                aliases.extend(service_aliases(item).get(net["NetworkID"], []))
            if db["host"] in aliases:
                db_candidates.append(item)
                break
    postgres = choose(
        "PostgreSQL do Chatwoot", db_candidates, lambda c: c["Name"], args.yes
    )
    project = (rails["Config"].get("Labels") or {}).get("com.docker.compose.project")
    if adapter == "compose" and project != (postgres["Config"].get("Labels") or {}).get(
        "com.docker.compose.project"
    ):
        raise InspectionError("Rails e PostgreSQL precisam pertencer ao mesmo projeto.")
    common = sorted(set(rails_nets) & set(postgres["NetworkSettings"]["Networks"]))
    internal = choose("Rede do Chatwoot", common, str, args.yes)
    internal_host = service_name(rails, adapter)
    network = internal
    url = inventory.get("url")
    if not url:
        raise InspectionError("FRONTEND_URL ausente no Chatwoot.")
    chatwoot_url = f"http://{internal_host}:3000"
    if adapter == "swarm" and inventory.get("force_ssl"):
        if urlsplit(url).scheme != "https":
            raise InspectionError(
                "FORCE_SSL exige FRONTEND_URL HTTPS no Chatwoot. "
                "Corrija a origem antes de instalar."
            )
        # Com FORCE_SSL o Rails responde 301 a chamadas HTTP diretas, que não passam
        # pelo proxy que envia X-Forwarded-Proto; usa a origem pública HTTPS.
        chatwoot_url = url
    entrypoint = "websecure"
    if adapter == "swarm":
        spec = inspect("service", service_name(rails, adapter))["Spec"]
        labels = spec.get("Labels") or {}
        routers = []
        for key, rule in labels.items():
            if (
                key.startswith("traefik.http.routers.")
                and key.endswith(".rule")
                and f"`{urlsplit(url).hostname}`" in rule
            ):
                prefix = key.removesuffix(".rule")
                points = labels.get(prefix + ".entrypoints", "").split(",")
                routers.extend(p for p in points if p)
        entrypoint = choose("Entrypoint Traefik", sorted(set(routers)), str, args.yes)
        network = proxy_network(docker, service_name(rails, adapter))
        if network not in rails_nets:
            raise InspectionError("Rede Traefik não está conectada ao Rails.")
    else:
        # Preservar o contrato Compose: gateway HTTP, sem editar proxy preexistente.
        if not args.public_url and terminal.interactive() and not args.yes:
            print(
                "Informe o endereço que sua equipe usará "
                "para abrir o Chatwoot com Kanban."
            )
            args.public_url = input(
                "Endereço de acesso (ex.: http://IP-DA-VPS:18080): "
            ).strip()
        if not args.public_url:
            raise InspectionError(
                "Compose exige --public-url http://HOST:PORTA para o gateway próprio. "
                "Use --listen-host 0.0.0.0 para acesso externo. "
                "HTTPS/proxy preexistente não é alterado automaticamente."
            )
        url = args.public_url
        if args.listen_host is None:
            args.listen_host = (
                "127.0.0.1"
                if urlsplit(url).hostname in ("localhost", "127.0.0.1")
                else "0.0.0.0"
            )
    return Deployment(
        adapter=adapter,
        name="chatwoot-kanban",
        context="default",
        accounts=accounts,
        image=image,
        public_url=url,
        chatwoot_url=chatwoot_url,
        chatwoot_service=service_name(rails, adapter),
        chatwoot_database_service=service_name(postgres, adapter),
        chatwoot_database=db["database"],
        chatwoot_database_user=db["username"],
        chatwoot_project=project if adapter == "compose" else None,
        chatwoot_network=internal,
        network=network,
        rails_wrapper=wrapper,
        tls=urlsplit(url).scheme == "https",
        entrypoint=entrypoint,
        listen_host=args.listen_host or "127.0.0.1",
        listen_port=urlsplit(url).port or 80,
    )


def parser() -> argparse.ArgumentParser:
    """Expõe apenas escolhas operacionais necessárias ao fluxo rápido."""
    result = argparse.ArgumentParser(description="Instalar Kanban na VPS com Chatwoot")
    result.add_argument(
        "operation",
        nargs="?",
        default=None,
        choices=["install", "update", "status", "uninstall"],
    )
    result.add_argument("--yes", action="store_true", help="Confirmar sem perguntas")
    result.add_argument(
        "--dry-run", action="store_true", help="Somente conferir o plano"
    )
    result.add_argument("--container", help="Container Rails quando houver vários")
    accounts = result.add_mutually_exclusive_group()
    accounts.add_argument("--accounts", nargs="+", type=int, help="IDs das contas")
    accounts.add_argument(
        "--all-accounts", action="store_true", help="Ativar todas as contas existentes"
    )
    result.add_argument(
        "--details",
        action="store_true",
        help="Mostrar diagnóstico técnico e plano JSON",
    )
    result.add_argument(
        "--rails-wrapper", nargs="+", help="Wrapper de segredos do Rails"
    )
    result.add_argument("--public-url", help="Origem HTTP do gateway Compose")
    result.add_argument("--listen-host")
    return result


def summary(config: Deployment, args: argparse.Namespace) -> None:
    """Mostra apenas o destino e as contas que receberão a integração."""
    names = getattr(args, "account_names", {})
    print(f"\n  Chatwoot: {terminal.clean(config.public_url)}")
    print(f"  Contas selecionadas: {len(config.accounts)}")
    for account in config.accounts:
        print(f"    • {terminal.clean(names.get(account, f'Conta #{account}'))}")
    print()


def show_status(result: dict, details: bool) -> None:
    """Exibe saúde sem confundir sucesso de provisionamento com disponibilidade."""
    if details:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result.get("healthy"):
        print("✓ Kanban funcionando em todas as contas selecionadas.")
    else:
        print(
            "O Kanban ainda não está pronto. Execute status --details para diagnóstico."
        )


def run(args: argparse.Namespace, root: Path = ROOT) -> int:
    """Planeja, confirma e delega ao mesmo ciclo de vida dos adaptadores."""
    image = os.environ.get("KANBAN_RUNTIME_IMAGE", "")
    if not re.fullmatch(
        r"ghcr.io/vitorpaimio/chatwoot-kanban@sha256:[a-f0-9]{64}", image
    ):
        raise InspectionError("A imagem do instalador não informa runtime por digest.")
    config_path = root / "installation.json"
    guard = State(root / "bootstrap")
    lifecycle = None
    try:
        guard.lock()
        print("\n  CHATWOOT KANBAN\n  Suas negociações dentro do Chatwoot.\n")
        if args.operation is None:
            if terminal.interactive() and not args.yes and not args.dry_run:
                existing = config_path.exists()
                operations = (
                    ["install", "status", "update", "uninstall"]
                    if existing
                    else ["install"]
                )
                labels = (
                    [
                        "Iniciar / retomar o Kanban",
                        "Verificar funcionamento",
                        "Atualizar",
                        "Remover integração",
                    ]
                    if existing
                    else ["Instalar e ativar o Kanban"]
                )
                args.operation = operations[
                    terminal.select("O que você quer fazer?", labels)[0]
                ]
            else:
                args.operation = "install"
        if config_path.exists():
            print("1/4  Carregando sua instalação…", flush=True)
            config = Deployment.model_validate_json(config_path.read_text())
            if args.accounts or args.all_accounts:
                raise InspectionError(
                    "Esta instalação já tem contas salvas. A seleção de contas é feita "
                    "na primeira instalação; nenhuma conta foi alterada."
                )
            if args.operation == "update":
                config = config.model_copy(update={"image": image})
        elif args.operation != "install":
            raise InspectionError(
                "Instalação não encontrada. Execute install primeiro."
            )
        else:
            print("1/4  Encontrando seu Chatwoot…", flush=True)
            config = discover(args, image)
        cls = ComposeLifecycle if config.adapter == "compose" else Lifecycle
        lifecycle = cls(config, root / "state")
        lifecycle.progress = lambda message: print(f"  {message}", flush=True)
        if args.operation == "status":
            lifecycle.preflight()
            result = lifecycle.status()
            show_status(result, args.details)
            return 0 if result.get("healthy") else 2
        print("2/4  Conferindo se está tudo pronto…", flush=True)
        plan = lifecycle.plan(args.operation, config.network)
        summary(config, args)
        if args.details:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        if plan["blocked"]:
            raise InspectionError(
                "Encontramos uma configuração incompatível. Nada foi instalado. "
                "Execute novamente com --dry-run --details para conferir."
            )
        if args.dry_run:
            print("Verificação concluída. Nenhuma instalação foi aplicada.")
            return 0
        if not args.yes:
            if not terminal.interactive():
                raise InspectionError(
                    "Use terminal interativo ou --yes para confirmar."
                )
            action = {
                "install": "Instalar e ativar nas contas selecionadas",
                "update": "Atualizar o Kanban com backup",
                "uninstall": "Remover integração e preservar os dados",
            }[args.operation]
            if (
                terminal.select(
                    f"Continuar com {len(config.accounts)} conta(s) selecionada(s)?",
                    ["Cancelar", action],
                    context=config.public_url,
                )[0]
                == 0
            ):
                print("Cancelado. Nenhum recurso Chatwoot alterado.")
                return 0
        if args.operation in ("install", "update"):
            print("3/4  Preparando o Kanban…", flush=True)
            docker("pull", config.image)
        write_private(config_path, config.model_dump_json(indent=2).encode())
        lifecycle.state.lock()
        if args.operation == "uninstall":
            result = lifecycle.uninstall(config.network, False, False)
        else:
            print("4/4  Instalando e ativando suas contas…", flush=True)
            result = lifecycle.install(args.operation, config.network)
        if args.details:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.operation != "uninstall" and result.get("healthy") is not True:
            show_status(result, False)
            return 2
        if args.operation == "uninstall":
            print("✓ Integração removida. Dados e backups preservados.")
        else:
            print(f"\n✓ Kanban pronto em {len(config.accounts)} conta(s)!")
            print(
                f"Abra {terminal.clean(config.public_url)} e acesse Pipeline → Kanban."
            )
        return 0
    except (Exception, KeyboardInterrupt):
        if (
            lifecycle
            and hasattr(lifecycle.state, "_lock")
            and lifecycle.state.data.get("status")
            in ("backing_up", "installing", "updating", "uninstalling")
        ):
            lifecycle.state.save(status="failed")
        raise
    finally:
        if lifecycle:
            lifecycle.state.close()
        guard.close()


def main() -> int:
    """Retorna diagnóstico seguro sem imprimir ambiente ou credenciais."""
    args = parser().parse_args()
    try:
        return run(args)
    except (terminal.CancelledError, KeyboardInterrupt):
        print(
            "\nOperação cancelada. Se a instalação já começou, "
            "execute status antes de retomar."
        )
        return 130
    except InspectionError as exc:
        print(str(exc), file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError, ValidationError):
        print(
            "Não foi possível concluir. Confira o ambiente e o estado da instalação.",
            file=sys.stderr,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
