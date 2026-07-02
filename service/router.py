"""Endpointy dartscore jako `APIRouter` do wpięcia w istniejący backend FastAPI.

Ponieważ backend autora to Python/FastAPI, moduł wizyjny wpina się bezpośrednio
(bez osobnego mikroserwisu): w swojej aplikacji robisz

    from service.router import create_darts_router
    app.include_router(create_darts_router(prefix="/darts"))

Cała logika wizyjna żyje w pakiecie `dartscore` i jest testowana niezależnie —
ten moduł tylko dekoduje wejście (base64), woła pipeline i serializuje wynik.

Endpointy (względem `prefix`):
    POST {prefix}/calibrate           -> kalibracja z klatek pustej tarczy
    GET  {prefix}/calibration/status  -> stan kalibracji
    POST {prefix}/score-throw         -> klatki (before/after) -> Hit JSON
    WS   {prefix}/ws/hits             -> strumień trafień na żywo
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from dartscore.config import BoardConfig, load_board_config, load_cameras_config
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
from .schemas import ThrowRequest, FrameSet, HitResponse, Position, CalibrationResponse


class DartsService:
    """Stan i logika serwisu (kalibracja + pipeline + klienci WebSocket).

    Trzymany poza modułem, aby dało się mieć wiele instancji / wstrzykiwać go w
    testach i w cudzej aplikacji FastAPI.
    """

    def __init__(
        self,
        calibration_path: str | Path | None = None,
        board: Optional[BoardConfig] = None,
    ) -> None:
        self.calibration_path = Path(
            calibration_path or os.environ.get("DARTSCORE_CALIBRATION", "calibration.json")
        )
        self.board = board or load_board_config()
        self.pipeline: Optional[ThrowPipeline] = None
        self.ws_clients: set[WebSocket] = set()
        self._load_pipeline_if_available()

    # -- zarządzanie stanem --------------------------------------------------

    def _try_load_cameras(self):
        try:
            return load_cameras_config()
        except FileNotFoundError:
            return None

    def _load_pipeline_if_available(self) -> None:
        if self.calibration_path.exists():
            calib = load_calibration(self.calibration_path)
            self.pipeline = ThrowPipeline(self.board, calib, cameras=self._try_load_cameras())

    def calibrate(self, images: dict[str, np.ndarray]) -> Calibration:
        calib = BoardCalibrator(self.board).calibrate(images)
        save_calibration(calib, self.calibration_path)
        self.pipeline = ThrowPipeline(self.board, calib, cameras=self._try_load_cameras())
        return calib

    def score_throw(self, before: dict[str, np.ndarray], after: dict[str, np.ndarray]) -> ThrowResult:
        if self.pipeline is None:
            raise NotCalibrated("Brak kalibracji — wykonaj POST /calibrate")
        return self.pipeline.process_pair(before, after)

    async def broadcast(self, response: HitResponse) -> None:
        dead: list[WebSocket] = []
        for ws in self.ws_clients:
            try:
                await ws.send_json(response.model_dump())
            except Exception:  # pragma: no cover - klient się rozłączył
                dead.append(ws)
        for ws in dead:
            self.ws_clients.discard(ws)


# -- pomocnicze: dekodowanie obrazów i mapowanie wyników ---------------------


def decode_image(b64: str) -> np.ndarray:
    """Zdekoduj obraz base64 (opcjonalnie z prefiksem data URI) do BGR ndarray."""
    if "," in b64 and b64.strip().startswith("data:"):
        b64 = b64.split(",", 1)[1]
    raw = base64.b64decode(b64)
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Nie udało się zdekodować obrazu base64")
    return img


def decode_frames(frames: dict[str, str]) -> dict[str, np.ndarray]:
    return {cid: decode_image(b64) for cid, b64 in frames.items()}


def result_to_response(result: ThrowResult) -> HitResponse:
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


def to_http(exc: DartScoreError) -> HTTPException:
    """Zmapuj wyjątki domenowe na kody HTTP."""
    if isinstance(exc, (NotCalibrated, BoardNotDetected)):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, CameraOffline):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, AmbiguousHit):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


# -- fabryka routera ---------------------------------------------------------


def create_darts_router(
    service: Optional[DartsService] = None,
    prefix: str = "",
    calibration_path: str | Path | None = None,
) -> APIRouter:
    """Zbuduj APIRouter z endpointami dartscore, gotowy do `app.include_router`.

    Args:
        service: gotowa instancja DartsService (albo None -> utworzona domyślna).
        prefix: prefiks ścieżek (np. "/darts").
        calibration_path: ścieżka pliku kalibracji (gdy tworzymy domyślny service).
    """
    svc = service or DartsService(calibration_path=calibration_path)
    router = APIRouter(prefix=prefix, tags=["dartscore"])

    @router.get("/calibration/status", response_model=CalibrationResponse)
    def calibration_status() -> CalibrationResponse:
        if svc.pipeline is None:
            return CalibrationResponse(calibrated=False, message="Brak kalibracji — wykonaj POST /calibrate")
        calib = svc.pipeline.calibration
        return CalibrationResponse(
            calibrated=True,
            sector20_offset_deg=calib.sector20_offset_deg,
            cameras=list(calib.cameras.keys()),
        )

    @router.post("/calibrate", response_model=CalibrationResponse)
    def calibrate(payload: FrameSet) -> CalibrationResponse:
        try:
            calib = svc.calibrate(decode_frames(payload.frames))
        except DartScoreError as exc:
            raise to_http(exc)
        return CalibrationResponse(
            calibrated=True,
            sector20_offset_deg=calib.sector20_offset_deg,
            cameras=list(calib.cameras.keys()),
            message="Kalibracja zapisana",
        )

    @router.post("/score-throw", response_model=HitResponse)
    async def score_throw(payload: ThrowRequest) -> HitResponse:
        try:
            result = svc.score_throw(decode_frames(payload.before), decode_frames(payload.after))
        except DartScoreError as exc:
            raise to_http(exc)
        response = result_to_response(result)
        await svc.broadcast(response)
        return response

    @router.websocket("/ws/hits")
    async def ws_hits(ws: WebSocket) -> None:
        await ws.accept()
        svc.ws_clients.add(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            svc.ws_clients.discard(ws)

    return router
