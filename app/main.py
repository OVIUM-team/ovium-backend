from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.routes.animals import router as animals_router
from app.routes.ranches import router as ranches_router
from app.routes.auth import router as auth_router
from app.routes.health import router as health_router
from app.routes.health_events import router as health_events_router
from app.routes.weights import router as weights_router

app = FastAPI(title="OVIUM API")
app.state.settings = Settings()
if app.state.settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app.state.settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(ranches_router)
app.include_router(animals_router)
app.include_router(health_events_router)
app.include_router(weights_router)
