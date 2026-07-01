"""Serwis FastAPI: REST (kalibracja, punktacja rzutu) + WebSocket (trafienia na żywo).

Warstwa ta tylko dekoduje wejście, woła pipeline z pakietu `dartscore` i serializuje
wynik — cała logika wizyjna żyje w `dartscore` i jest testowana niezależnie.

Backend Node/JS woła te endpointy (obrazy przesyłane jako base64 w JSON):
    POST /calibrate            -> zbuduj i zapisz kalibrację z klatek pustej tarczy
    GET  /calibration/status   -> stan kalibracji
    POST /score-throw          -> klatki (before/after) -> Hit JSON
    WS   /ws/hits              -> strumień trafień na żywo

Uruchomienie:  uvicorn service.api:app --reload
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from dartscore.config import load_board_config, load_cameras_config
from dartscore.calibration.board_calibrator import BoardCalibrator
from dartscore.calibration.store import Calibration, save_calibration, load_calibration
from dartscore.pipeline import ThrowPipeline, ThrowResult
from dartscore.errors import (
    DartScoreError,
    BoardNotDetected,
    CameraOffline,
    AmbiguousHit,
    NotCalibrated,
)
from .schemas import (
    ThrowRequest,
    FrameSet,
    HitResponse,
    Position,
    CalibrationResponse,
)

CALIBRATION_PATH = Path(os.environ.get("DARTSCORE_CALIBRATION", "calibration.json"))

app = FastAPI(title="dartscore", version="0.1.0")

# Stan procesu: geometria, kalibracja i pipeline trzymane w pamięci.
_board = load_board_config()
_pipeline: Optional[ThrowPipeline] = None
_ws_clients: set[WebSocket] = set()


def _load_pipeline_if_available() -> None:
    global _pipeline
    if CALIBRATION_PATH.exists():
        calib = load_calibration(CALIBRATION_PATH)
        cams = _try_load_cameras()
        _pipeline = ThrowPipeline(_board, calib, cameras=cams)


def _try_load_cameras():
    try:
        return load_cameras_config()
    except FileNotFoundError:
        return None


_load_pipeline_if_available()


def _decode(b64: str) -> np.ndarray:
    """Zdekoduj obraz base64 (opcjonalnie z prefiksem data URI) do BGR ndarray."""
    if "," in b64 and b64.strip().startswith("data:"):
        b64 = b64.split(",", 1)[1]
    raw = base64.b64decode(b64)
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Nie udało się zdekodować obrazu base64")
    return img


def _decode_frames(frames: dict[str, str]) -> dict[str, np.ndarray]:
    return {cid: _decode(b64) for cid, b64 in frames.items()}


def _result_to_response(result: ThrowResult) -> HitResponse:
    hit, fused = result.hit, result.fused
    return HitResponse(
        sector=hit.sector,
        ring=hit.ring,
        multiplier=hit.multiplier,
        score=hit.score,
        confidence=fused.confidence,
        near_boundary=hit.near_boundary,
        position=Position(
            angle_deg=fused.angle_deg, radius_mm=fused.radius_mm, x_mm=fused.x_mm, y_mm=fused.y_mm
        ),
        cameras_used=fused.cameras_used,
    )


@app.get("/calibration/status", response_model=CalibrationResponse)
def calibration_status() -> CalibrationResponse:
    if _pipeline is None:
        return CalibrationResponse(calibrated=False, message="Brak kalibracji — wykonaj POST /calibrate")
    calib = _pipeline.calibration
    return CalibrationResponse(
        calibrated=True,
        sector20_offset_deg=calib.sector20_offset_deg,
        cameras=list(calib.cameras.keys()),
    )


@app.post("/calibrate", response_model=CalibrationResponse)
def calibrate(payload: FrameSet) -> CalibrationResponse:
    """Zbuduj kalibrację z klatek pustej tarczy (mapa camera_id -> base64) i zapisz."""
    global _pipeline
    images = _decode_frames(payload.frames)
    calibrator = BoardCalibrator(_board)
    try:
        calib: Calibration = calibrator.calibrate(images)
    except DartScoreError as exc:
        raise _to_http(exc)
    save_calibration(calib, CALIBRATION_PATH)
    _pipeline = ThrowPipeline(_board, calib, cameras=_try_load_cameras())
    return CalibrationResponse(
        calibrated=True,
        sector20_offset_deg=calib.sector20_offset_deg,
        cameras=list(calib.cameras.keys()),
        message="Kalibracja zapisana",
    )


@app.post("/score-throw", response_model=HitResponse)
async def score_throw(payload: ThrowRequest) -> HitResponse:
    """Klatki przed/po rzucie -> Hit JSON. Rozsyła wynik też do klientów WS."""
    if _pipeline is None:
        raise HTTPException(status_code=409, detail="Brak kalibracji — wykonaj POST /calibrate")
    try:
        result = _pipeline.process_pair(_decode_frames(payload.before), _decode_frames(payload.after))
    except DartScoreError as exc:
        raise _to_http(exc)
    response = _result_to_response(result)
    await _broadcast(response)
    return response


@app.websocket("/ws/hits")
async def ws_hits(ws: WebSocket) -> None:
    """Strumień trafień na żywo do frontu."""
    await ws.accept()
    _ws_clients.add(ws)
    try:
        while True:
            # Pozwalamy klientowi trzymać połączenie; nie oczekujemy wiadomości.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


async def _broadcast(response: HitResponse) -> None:
    dead: list[WebSocket] = []
    for ws in _ws_clients:
        try:
            await ws.send_json(response.model_dump())
        except Exception:  # pragma: no cover - klient się rozłączył
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


def _to_http(exc: DartScoreError) -> HTTPException:
    """Zmapuj wyjątki domenowe na kody HTTP."""
    if isinstance(exc, (NotCalibrated, BoardNotDetected)):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, CameraOffline):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, AmbiguousHit):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))
