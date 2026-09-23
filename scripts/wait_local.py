"""Aguarda Rails, proxy e API antes de anunciar a inicialização local."""

import time
import urllib.error
import urllib.request

for _ in range(60):
    try:
        with urllib.request.urlopen("http://localhost:3000/app/login", timeout=2) as r:
            ready = r.status == 200
        try:
            urllib.request.urlopen(
                "http://localhost:3000/kanban/session?account=1", timeout=2
            )
        except urllib.error.HTTPError as error:
            if ready and error.code == 401:
                print(
                    "Pronto: http://localhost:3000 — entre no Chatwoot e abra Kanban."
                )
                break
    except (OSError, urllib.error.URLError):
        pass
    time.sleep(1)
else:
    raise SystemExit("Serviços ainda indisponíveis. Consulte scripts/local.sh status.")
