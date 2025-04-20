from fastapi import APIRouter

from . import appointments, clients, messages, notifications, services, working_periods

api_router = APIRouter()

api_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(services.router, prefix="/services", tags=["services"])
api_router.include_router(working_periods.router, prefix="/working_periods", tags=["working_periods"])
