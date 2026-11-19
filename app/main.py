from fastapi import FastAPI

from app.config import Settings
from app.routes.health import router as health_router

app = FastAPI(title="OVIUM API")
app.state.settings = Settings()
app.include_router(health_router)
