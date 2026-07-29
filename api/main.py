import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import scans

app = FastAPI(title="Momentum Hunter API")

_allowed_origins = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins or ["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(scans.router)


@app.get("/health")
def health():
    return {"status": "ok"}
