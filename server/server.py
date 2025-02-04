from fastapi import FastAPI
from server.database import init_db
from server.routes import router

app = FastAPI(title="AutoService API")

@app.on_event("startup")
async def startup():
    await init_db()

app.include_router(router)
