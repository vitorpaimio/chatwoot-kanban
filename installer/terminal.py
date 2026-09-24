"""Seletores de terminal para o assistente, sem dependências adicionais."""

import curses
import sys
import unicodedata
from contextlib import suppress

from installer.swarm import InspectionError


class CancelledError(Exception):
    """Indica cancelamento antes de aplicar a escolha."""


def interactive() -> bool:
    """Exige entrada e saída conectadas ao terminal."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def clean(value: object) -> str:
    """Remove controles de nomes externos antes de exibi-los no terminal."""
    return "".join(
        char if not unicodedata.category(char).startswith("C") else " "
        for char in str(value)
    )


def _menu(
    screen, title: str, labels: list[str], multiple: bool, context: str = ""
) -> list[int]:
    screen.keypad(True)
    with suppress(curses.error):
        curses.curs_set(0)
    accent = curses.A_BOLD
    focus = curses.A_REVERSE
    with suppress(curses.error):
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)
        accent = curses.color_pair(1) | curses.A_BOLD
        focus = curses.color_pair(2) | curses.A_BOLD
    cursor = 0
    selected: set[int] = set()
    message = ""
    while True:
        height, width = screen.getmaxyx()
        screen.erase()

        def line(
            y: int,
            text: str,
            active: bool = False,
            height: int = height,
            width: int = width,
        ) -> None:
            if 0 <= y < height - 1 and width > 2:
                with suppress(curses.error):
                    screen.addnstr(
                        y,
                        1,
                        clean(text),
                        width - 2,
                        focus if active else accent if y == 1 else curses.A_NORMAL,
                    )

        line(1, "CHATWOOT KANBAN")
        line(2, "─" * min(60, max(0, width - 2)))
        line(3, title)
        if context:
            line(4, context)
        options = (["Selecionar todas"] if multiple else []) + labels
        visible = max(1, height - 10)
        start = max(0, min(cursor - visible + 1, len(options) - visible))
        for index in range(start, min(start + visible, len(options))):
            marker = ""
            if multiple:
                checked = (
                    len(selected) == len(labels)
                    if index == 0
                    else index - 1 in selected
                )
                marker = "[x] " if checked else "[ ] "
            line(
                5 + index - start,
                f"{'›' if index == cursor else ' '} {marker}{options[index]}",
                index == cursor,
            )
        if multiple:
            line(
                height - 4,
                message or f"{len(selected)} de {len(labels)} contas selecionadas",
            )
            line(height - 3, "↑ ↓ navegar · Espaço marcar · A todas · Enter continuar")
        else:
            line(height - 3, "↑ ↓ navegar · Enter escolher")
        line(height - 2, "Esc cancelar")
        screen.refresh()
        key = screen.getch()
        if key in (27, 3):
            raise CancelledError
        if key == curses.KEY_UP:
            cursor = (cursor - 1) % len(options)
        elif key == curses.KEY_DOWN:
            cursor = (cursor + 1) % len(options)
        elif multiple and (
            key in (ord("a"), ord("A")) or key == ord(" ") and cursor == 0
        ):
            selected = (
                set() if len(selected) == len(labels) else set(range(len(labels)))
            )
            message = ""
        elif multiple and key == ord(" "):
            index = cursor - 1
            selected.symmetric_difference_update({index})
            message = ""
        elif key in (10, 13, curses.KEY_ENTER):
            if not multiple:
                return [cursor]
            if selected:
                return sorted(selected)
            message = "Marque pelo menos uma conta para continuar."


def select(
    title: str, labels: list[str], *, multiple: bool = False, context: str = ""
) -> list[int]:
    """Seleciona por setas; restaura o terminal ao concluir ou cancelar."""
    if not labels:
        raise InspectionError("Nenhuma opção disponível.")
    if not interactive():
        raise InspectionError(
            "Abra um terminal interativo ou informe as opções por argumentos."
        )
    try:
        return curses.wrapper(_menu, title, labels, multiple, context)
    except curses.error:
        raise InspectionError(
            "O terminal não suporta o menu. Use --yes e --accounts ou --all-accounts."
        ) from None
