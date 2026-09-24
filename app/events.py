"""Um LISTEN PostgreSQL por processo com orçamento de assinantes SSE."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import TracebackType

import asyncpg
from fastapi import HTTPException

from app.config import settings


class EventLease:
    """Reserva síncrona que pode ser liberada mais de uma vez com segurança."""

    def __init__(self, hub: "EventHub", account: int) -> None:
        self.hub = hub
        self.account = account
        self.released = False

    def release(self) -> None:
        """Devolve o orçamento mesmo quando a resposta termina antes do gerador."""
        if self.released:
            return
        self.released = True
        self.hub.reserved -= 1
        remaining = self.hub.account_reserved[self.account] - 1
        if remaining:
            self.hub.account_reserved[self.account] = remaining
        else:
            del self.hub.account_reserved[self.account]

    def __enter__(self) -> "EventLease":
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.release()


class EventHub:
    """Compartilha notificações sem exceder limites por processo e conta."""

    def __init__(
        self, max_subscribers: int = 300, max_account_subscribers: int = 60
    ) -> None:
        if max_subscribers < 1 or max_account_subscribers < 1:
            raise ValueError("Os limites de assinantes devem ser positivos")
        self.connection = None
        self.lock = asyncio.Lock()
        self.subscribers = {}
        self.max_subscribers = max_subscribers
        self.max_account_subscribers = max_account_subscribers
        self.reserved = 0
        self.account_reserved: dict[int, int] = {}

    def lease(self, account: int) -> EventLease:
        """Reserva antes dos cabeçalhos HTTP, sem ceder o loop de eventos."""
        count = self.account_reserved.get(account, 0)
        if (
            self.reserved >= self.max_subscribers
            or count >= self.max_account_subscribers
        ):
            raise HTTPException(
                status_code=429,
                detail="Limite de conexões em tempo real atingido. Tente novamente.",
                headers={"Retry-After": "5"},
            )
        self.reserved += 1
        self.account_reserved[account] = count + 1
        return EventLease(self, account)

    def changed(self, _conn, _pid, _channel, payload):
        for signal in tuple(self.subscribers.get(payload, ())):
            signal.set()

    def terminated(self, _conn):
        self.connection = None
        for signals in self.subscribers.values():
            for signal in signals:
                signal.set()

    @asynccontextmanager
    async def subscribe(
        self, account: int, *, lease: EventLease | None = None
    ) -> AsyncIterator[asyncio.Event]:
        """Assina uma conta e libera a reserva em falhas ou cancelamentos."""
        if lease is None:
            lease = self.lease(account)
        elif lease.hub is not self or lease.account != account or lease.released:
            raise ValueError("Reserva inválida para esta assinatura")
        signal = asyncio.Event()
        key = str(account)
        try:
            async with self.lock:
                if self.connection is None:
                    connection = await asyncpg.connect(settings.database_url)
                    try:
                        await connection.add_listener("kanban_events", self.changed)
                        connection.add_termination_listener(self.terminated)
                    except BaseException:
                        await connection.close()
                        raise
                    self.connection = connection
                self.subscribers.setdefault(key, set()).add(signal)
            yield signal
        finally:
            signals = self.subscribers.get(key)
            if signals is not None:
                signals.discard(signal)
                if not signals:
                    del self.subscribers[key]
            lease.release()

    async def close(self):
        if self.connection:
            await self.connection.close()


hub = EventHub()
