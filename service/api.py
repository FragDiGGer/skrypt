"""Samodzielny serwis FastAPI dartscore (wariant „osobny proces").

Jeśli masz WŁASNY backend FastAPI, nie potrzebujesz tego pliku — wepnij endpointy
bezpośrednio (patrz service/router.py):

    from service.router import create_darts_router
    app.include_router(create_darts_router(prefix="/darts"))

Ten moduł jest wygodny, gdy chcesz uruchomić dartscore jako osobny serwis:

    uvicorn service.api:app --reload

CORS jest domyślnie otwarty na dev-serwer Vite (http://localhost:5173); listę
originów można nadpisać zmienną DARTS_CORS_ORIGINS (rozdzielone przecinkami).
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .router import create_darts_router

app = FastAPI(title="dartscore", version="0.1.0")

# CORS dla frontu React/Vite (dev). W produkcji ustaw DARTS_CORS_ORIGINS na swój host.
_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
_origins = [o.strip() for o in os.environ.get("DARTS_CORS_ORIGINS", _default_origins).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wszystkie endpointy dartscore (REST + WebSocket).
app.include_router(create_darts_router())
