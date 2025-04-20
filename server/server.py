import hashlib
from contextlib import asynccontextmanager
import os

from server.database import Base, engine
from fastapi import FastAPI, Depends, HTTPException, Request, APIRouter
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

from server.models import *

from typing import List, Callable, Optional

import redis.asyncio as redis

from server.endpoints import appointments, clients, services, notifications, messages, working_periods

def my_custom_key_builder(
    func: Callable,
    namespace: str = "",
    request:Request =None,
    response=None,
    args=(),
    kwargs=None
) -> str:
    print(f"namespace = '{namespace}'")
    raw_key = f"{namespace}:{func.__name__}:{request.url}"
    hashed = hashlib.md5(raw_key.encode()).hexdigest()
    return f"{raw_key}"

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
    redis_client = redis.Redis.from_url(redis_url)
    FastAPICache.init(RedisBackend(redis_client), prefix="fast_api", key_builder=my_custom_key_builder)
    yield
    await redis_client.close()

app = FastAPI(lifespan=lifespan)

app.include_router(services.router, prefix="/services", tags=["services"])
app.include_router(clients.router, prefix="/clients", tags=["clients"])
app.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(messages.router, prefix="/messages", tags=["messages"])
app.include_router(working_periods.router, prefix="/working_periods", tags=["working_periods"])