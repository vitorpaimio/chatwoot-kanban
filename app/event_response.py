"""Liberação do orçamento mesmo se o cliente abandonar antes do primeiro evento."""

import anyio
from starlette.responses import StreamingResponse

from app.events import EventLease


class EventResponse(StreamingResponse):
    def __init__(self, content, lease: EventLease, **kwargs):
        super().__init__(content, **kwargs)
        self.lease = lease

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            try:
                with anyio.CancelScope(shield=True):
                    await self.body_iterator.aclose()
            finally:
                self.lease.release()
