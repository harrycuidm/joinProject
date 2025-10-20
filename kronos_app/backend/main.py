"""FastAPI 入口。"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .schemas import PredictionRequest, PredictionResponse
from .services.prediction_service import PredictionService

LOGGER = logging.getLogger(__name__)

app = FastAPI(title="Kronos A股预测服务", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ServiceProvider:
    """懒加载服务。"""

    def __init__(self) -> None:
        self._service: Optional[PredictionService] = None

    def get_service(self) -> PredictionService:
        if self._service is None:
            self._service = PredictionService()
        return self._service


provider = ServiceProvider()


def get_service(settings: Settings = Depends(get_settings)) -> PredictionService:  # noqa: D401
    """依赖注入的服务工厂。"""

    _ = settings
    return provider.get_service()


@app.post("/api/predict", response_model=PredictionResponse, summary="预测并可选评估")
def predict(request: PredictionRequest, service: PredictionService = Depends(get_service)) -> PredictionResponse:
    try:
        if not request.horizons:
            request.horizons = service.settings.default_horizons
        prediction = service.predict(request)
        evaluation = service.evaluate(request, prediction)
        return PredictionResponse(prediction=prediction, evaluation=evaluation)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("预测失败")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/health", summary="健康检查")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {
        "status": "ok",
        "kronos_repo": settings.kronos_repo,
    }
