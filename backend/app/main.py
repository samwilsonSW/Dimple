from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import rounds, health

app = FastAPI(
    title="Dimple API",
    description="Golf Intelligence Backend",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(rounds.router)


@app.get("/")
def root():
    return {
        "name": "Dimple API",
        "version": "0.1.0",
        "docs": "/docs",
    }
