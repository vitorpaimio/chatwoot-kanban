"""Orçamento de SSE sem depender de rede ou banco de dados."""

import asyncio
from contextlib import AsyncExitStack
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import ClientDisconnect

from app.event_response import EventResponse
from app.events import EventHub


def fake_connection(monkeypatch):
    connection = AsyncMock()
    connection.add_termination_listener = lambda _callback: None
    connect = AsyncMock(return_value=connection)
    monkeypatch.setattr("app.events.asyncpg.connect", connect)
    return connection, connect


async def test_default_budget_supports_thirty_users_and_single_listener(monkeypatch):
    connection, connect = fake_connection(monkeypatch)
    hub = EventHub()
    async with AsyncExitStack() as stack:
        signals = [await stack.enter_async_context(hub.subscribe(1)) for _ in range(30)]
        assert hub.reserved == 30
        assert len(hub.subscribers["1"]) == 30
        connect.assert_awaited_once()
        connection.add_listener.assert_awaited_once()
        for _ in range(100):
            hub.changed(None, None, None, "1")
        assert all(signal.is_set() for signal in signals)
        for signal in signals:
            signal.clear()
        assert all(not signal.is_set() for signal in signals)
    assert hub.reserved == 0
    assert hub.account_reserved == {}
    assert hub.subscribers == {}


async def test_account_budget_isolated_and_released(monkeypatch):
    fake_connection(monkeypatch)
    hub = EventHub(max_subscribers=3, max_account_subscribers=1)
    async with hub.subscribe(1):
        with pytest.raises(HTTPException) as error:
            hub.lease(1)
        assert error.value.status_code == 429
        assert error.value.headers == {"Retry-After": "5"}
        async with hub.subscribe(2):
            assert hub.reserved == 2
    with hub.lease(1):
        assert hub.reserved == 1
    assert hub.reserved == 0


def test_process_budget_counts_reservations_before_subscription():
    hub = EventHub(max_subscribers=2, max_account_subscribers=2)
    first, second = hub.lease(1), hub.lease(2)
    with pytest.raises(HTTPException):
        hub.lease(3)
    first.release()
    first.release()
    with hub.lease(3):
        assert hub.reserved == 2
    second.release()
    assert hub.reserved == 0


async def test_connection_failure_releases_reservation(monkeypatch):
    monkeypatch.setattr(
        "app.events.asyncpg.connect", AsyncMock(side_effect=OSError("indisponível"))
    )
    hub = EventHub()
    with pytest.raises(OSError):
        async with hub.subscribe(1):
            pytest.fail("Conexão indisponível")
    assert hub.reserved == 0
    assert hub.account_reserved == {}


async def test_listener_failure_closes_connection_and_releases(monkeypatch):
    connection, _ = fake_connection(monkeypatch)
    connection.add_listener.side_effect = OSError("indisponível")
    hub = EventHub()
    with pytest.raises(OSError):
        async with hub.subscribe(1):
            pytest.fail("LISTEN indisponível")
    connection.close.assert_awaited_once()
    assert hub.connection is None
    assert hub.reserved == 0


async def test_cancellation_waiting_for_listener_releases(monkeypatch):
    fake_connection(monkeypatch)
    hub = EventHub()
    lease = hub.lease(1)

    async def subscribe():
        async with hub.subscribe(1, lease=lease):
            pytest.fail("O lock ainda não foi liberado")

    async with hub.lock:
        task = asyncio.create_task(subscribe())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert hub.reserved == 0
    assert hub.subscribers == {}


async def test_cancellation_active_subscription_releases(monkeypatch):
    fake_connection(monkeypatch)
    hub = EventHub()
    started = asyncio.Event()

    async def subscribe():
        async with hub.subscribe(1):
            started.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(subscribe())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert hub.reserved == 0
    assert hub.subscribers == {}


async def test_preallocated_lease_not_counted_twice(monkeypatch):
    fake_connection(monkeypatch)
    hub = EventHub(max_subscribers=1, max_account_subscribers=1)
    lease = hub.lease(1)
    async with hub.subscribe(1, lease=lease):
        assert hub.reserved == 1
    lease.release()
    assert hub.reserved == 0


async def test_response_send_failure_closes_subscriber_and_releases(monkeypatch):
    _, connect = fake_connection(monkeypatch)
    hub = EventHub()
    lease = hub.lease(1)
    closed = asyncio.Event()

    async def stream():
        try:
            async with hub.subscribe(1, lease=lease):
                yield "event: ready\ndata: {}\n\n"
        finally:
            closed.set()

    async def send(message):
        if message["type"] == "http.response.body":
            assert hub.reserved == 1
            assert len(hub.subscribers["1"]) == 1
            raise OSError("Cliente desconectado durante o envio")

    response = EventResponse(stream(), lease=lease)
    with pytest.raises(ClientDisconnect):
        await response(
            {"type": "http", "asgi": {"spec_version": "2.4"}},
            AsyncMock(),
            send,
        )
    connect.assert_awaited_once()
    assert closed.is_set()
    assert hub.reserved == 0
    assert hub.account_reserved == {}
    assert hub.subscribers == {}


async def test_response_cancelled_before_generator_releases(monkeypatch):
    _, connect = fake_connection(monkeypatch)
    hub = EventHub()
    lease = hub.lease(1)
    response_started = asyncio.Event()
    generator_started = False

    async def stream():
        nonlocal generator_started
        generator_started = True
        async with hub.subscribe(1, lease=lease):
            yield "event: ready\ndata: {}\n\n"

    async def send(message):
        assert message["type"] == "http.response.start"
        response_started.set()
        await asyncio.Event().wait()

    response = EventResponse(stream(), lease=lease)
    task = asyncio.create_task(
        response(
            {"type": "http", "asgi": {"spec_version": "2.4"}},
            AsyncMock(),
            send,
        )
    )
    await asyncio.wait_for(response_started.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not generator_started
    connect.assert_not_awaited()
    assert hub.reserved == 0
    assert hub.account_reserved == {}
    assert hub.subscribers == {}
