"""Um LISTEN PostgreSQL por processo; assinantes não recebem payloads do banco."""

import asyncio
from contextlib import asynccontextmanager

import asyncpg

from app.config import settings


class EventHub:
    def __init__(self):
        self.connection = None
        self.lock = asyncio.Lock()
        self.subscribers = {}

    def changed(self, _conn, _pid, _channel, payload):
        for signal in tuple(self.subscribers.get(payload, ())):
            signal.set()

    def terminated(self, _conn):
        self.connection = None
        for signals in self.subscribers.values():
            for signal in signals:
                signal.set()

    @asynccontextmanager
    async def subscribe(self, account: int):
        async with self.lock:
            if self.connection is None:
                self.connection = await asyncpg.connect(settings.database_url)
                await self.connection.add_listener("kanban_events", self.changed)
                self.connection.add_termination_listener(self.terminated)
            signal = asyncio.Event()
            self.subscribers.setdefault(str(account), set()).add(signal)
        try:
            yield signal
        finally:
            self.subscribers[str(account)].discard(signal)
            if not self.subscribers[str(account)]:
                del self.subscribers[str(account)]

    async def close(self):
        if self.connection:
            await self.connection.close()


hub = EventHub()
