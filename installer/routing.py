"""Descoberta da rede realmente compartilhada pelo Rails e Traefik."""

import json
from collections.abc import Callable

from installer.swarm import InspectionError


def proxy_network(run: Callable[..., str | bytes], rails_service: str) -> str:
    """Resolve label, configuração do provedor ou única rede comum comprovada."""

    def inspect(kind: str, name: str) -> dict:
        return json.loads(run(kind, "inspect", name))[0]

    rails = inspect("service", rails_service)["Spec"]
    services = run("service", "ls", "-q")
    if isinstance(services, bytes):
        services = services.decode()
    proxies = []
    for service in services.split():
        spec = inspect("service", service)["Spec"]
        image = spec.get("TaskTemplate", {}).get("ContainerSpec", {}).get("Image", "")
        if image.rsplit("/", 1)[-1].split(":", 1)[0].split("@", 1)[0] == "traefik":
            proxies.append(spec)
    if len(proxies) != 1:
        raise InspectionError("Não foi possível identificar um único Traefik no Swarm.")
    proxy = proxies[0]

    def networks(spec: dict) -> set[str]:
        return {
            inspect("network", net["Target"])["Name"]
            for net in spec.get("TaskTemplate", {}).get("Networks", [])
            if net.get("Target")
        } - {"ingress"}

    common = networks(rails) & networks(proxy)
    container = proxy["TaskTemplate"]["ContainerSpec"]
    env = dict(item.split("=", 1) for item in container.get("Env", []) if "=" in item)
    defaults = []
    args = container.get("Args", [])
    for provider in ("swarm", "docker"):
        flag = f"--providers.{provider}.network"
        value = env.get(f"TRAEFIK_PROVIDERS_{provider.upper()}_NETWORK")
        for index, arg in enumerate(args):
            if arg.startswith(flag + "="):
                value = arg.split("=", 1)[1]
            elif arg == flag and index + 1 < len(args):
                value = args[index + 1]
        if value:
            defaults.append(value)
    labels = rails.get("Labels") or {}
    selected = labels.get("traefik.swarm.network") or labels.get(
        "traefik.docker.network"
    )
    if not selected:
        candidates = set(defaults) if defaults else common
        if len(candidates) != 1:
            raise InspectionError(
                "Rede do Traefik ambígua; configure a rede do serviço Rails."
            )
        selected = next(iter(candidates))
    if selected not in common:
        raise InspectionError(
            "A rede selecionada não é compartilhada por Rails e Traefik."
        )
    return selected
