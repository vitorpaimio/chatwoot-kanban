"""Navegação, multisseleção e cancelamento do assistente de terminal."""

import curses

import pytest

from installer import terminal


class Screen:
    def __init__(self, keys, height=24):
        self.keys = iter(keys)
        self.height = height
        self.lines = []

    def keypad(self, _enabled):
        pass

    def getmaxyx(self):
        return self.height, 80

    def erase(self):
        pass

    def addnstr(self, _y, _x, text, _length, _style):
        self.lines.append(text)

    def refresh(self):
        pass

    def getch(self):
        return next(self.keys)


def test_arrows_select_and_wrap():
    screen = Screen([curses.KEY_UP, 10])
    assert terminal._menu(screen, "Ação", ["Instalar", "Cancelar"], False) == [1]


def test_all_accounts_can_be_selected_then_one_unchecked():
    screen = Screen([ord(" "), curses.KEY_DOWN, ord(" "), 10])
    assert terminal._menu(screen, "Contas", ["A", "B", "C"], True) == [1, 2]


def test_empty_selection_stays_in_menu_and_all_shortcut_toggles():
    screen = Screen([10, ord("a"), ord("a"), 10, ord("a"), 10])
    assert terminal._menu(screen, "Contas", ["A", "B"], True) == [0, 1]
    assert "Marque pelo menos uma conta para continuar." in screen.lines


def test_many_accounts_scroll_on_small_terminal():
    screen = Screen([curses.KEY_DOWN] * 25 + [ord(" "), 10], height=15)
    assert terminal._menu(screen, "Contas", [str(i) for i in range(40)], True) == [24]
    assert any("[x] 24" in line for line in screen.lines)


@pytest.mark.parametrize("key", [27, 3])
def test_cancel_does_not_return_a_selection(key):
    with pytest.raises(terminal.CancelledError):
        terminal._menu(Screen([key]), "Contas", ["A"], True)


def test_external_names_cannot_inject_terminal_controls():
    assert terminal.clean("Cliente\x1b[2J\n\u202eA") == "Cliente [2J  A"
