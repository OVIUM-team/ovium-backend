from fastapi import FastAPI

from app.config import Settings
from app.routes.animals import router as animals_router
from app.routes.ranches import router as ranches_router
from app.routes.auth import router as auth_router
from app.routes.health import router as health_router

app = FastAPI(title="OVIUM API")
app.state.settings = Settings()
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(ranches_router)
app.include_router(animals_router)
