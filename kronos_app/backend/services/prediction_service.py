"""业务逻辑服务。"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Iterable, List, Tuple

try:  # pragma: no cover - prefer real numpy
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover
    class _NumpyStub:
        ndarray = tuple  # type: ignore[assignment]
        integer = int

    np = _NumpyStub()  # type: ignore

try:  # pragma: no cover - exercised via tests with stub fallback
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    from .. import pandas_stub as pd  # type: ignore

from ..config import get_settings
from ..schemas import EvaluationResult, PredictionRequest, PredictionResult
from .data_provider import fetch_daily_bars, slice_history
from .kronos_runner import KronosRunner

LOGGER = logging.getLogger(__name__)


class PredictionService:
    """面向 FastAPI 的预测服务。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.runner = KronosRunner.initialize()

    def _prepare_history(self, request: PredictionRequest) -> pd.DataFrame:
        lookback = max(request.horizons) * 40
        history = fetch_daily_bars(
            request.ticker,
            end_date=request.evaluation_anchor or date.today(),
            lookback_days=lookback,
        )
        return history

    def predict(self, request: PredictionRequest) -> PredictionResult:
        history = self._prepare_history(request)
        kronos_output = self.runner.predict_returns(history=history, horizons=request.horizons)
        (
            aggregated_changes,
            horizon_returns,
            horizon_probabilities,
        ) = self._format_output(history, kronos_output)
        return PredictionResult(
            ticker=request.ticker,
            horizons=request.horizons,
            daily_changes=aggregated_changes,
            horizon_returns=horizon_returns,
            horizon_probabilities=horizon_probabilities,
            metadata={
                "source": "Kronos",
                "history_rows": len(history),
            },
        )

    def _format_output(
        self,
        history: pd.DataFrame,
        kronos_output: Dict[int, Any],
    ) -> Tuple[Dict[str, Dict[str, float]], Dict[int, Dict[str, float]], Dict[int, Dict[str, float]]]:
        aggregated: Dict[str, Dict[str, float]] = {}
        horizon_returns: Dict[int, Dict[str, float]] = {}
        horizon_probabilities: Dict[int, Dict[str, float]] = {}
        last_date = history.index[-1]
        for horizon in sorted(int(h) for h in kronos_output.keys()):
            output = kronos_output[horizon]
            normalized, probabilities = self._normalize_prediction(last_date, output)
            horizon_map: Dict[str, float] = {}
            horizon_prob_map: Dict[str, float] = {}
            for key, value in normalized:
                horizon_map[key] = value
                if key not in aggregated:
                    aggregated[key] = {
                        "return": value,
                        "probability": probabilities.get(key, 0.0),
                    }
                elif key in probabilities and aggregated[key].get("probability", 0.0) == 0.0:
                    aggregated[key]["probability"] = probabilities[key]
                if key in probabilities:
                    horizon_prob_map[key] = probabilities[key]
            horizon_returns[horizon] = horizon_map
            if horizon_prob_map:
                horizon_probabilities[horizon] = horizon_prob_map
        return aggregated, horizon_returns, horizon_probabilities

    def _normalize_prediction(
        self,
        last_date: pd.Timestamp,
        output: Any,
    ) -> Tuple[List[Tuple[str, float]], Dict[str, float]]:
        if isinstance(output, dict):
            predicted_series = (
                output.get("returns")
                or output.get("predicted_returns")
                or output.get("values")
                or output
            )
            probability_series = (
                output.get("probability")
                or output.get("probabilities")
                or output.get("probs")
            )
        else:
            predicted_series = output
            probability_series = None
        normalized = self._normalize_series(predicted_series, last_date)
        probabilities = self._normalize_probabilities(probability_series, last_date)
        return normalized, probabilities

    def _normalize_series(
        self,
        predicted_series: Any,
        last_date: pd.Timestamp,
    ) -> List[Tuple[str, float]]:
        if isinstance(predicted_series, pd.Series):
            iterator: Iterable[Tuple[Any, Any]] = predicted_series.items()
        elif isinstance(predicted_series, dict):
            iterator = predicted_series.items()
        elif isinstance(predicted_series, (list, tuple, np.ndarray)):
            iterator = enumerate(predicted_series, start=1)
        else:
            raise RuntimeError(f"不支持的 Kronos 输出类型: {type(predicted_series)}")
        normalized: List[Tuple[str, float]] = []
        for idx, value in iterator:
            key = self._index_to_iso(last_date, idx)
            normalized.append((key, float(value)))
        return normalized

    def _normalize_probabilities(
        self,
        probability_series: Any,
        last_date: pd.Timestamp,
    ) -> Dict[str, float]:
        if probability_series is None:
            return {}
        if isinstance(probability_series, pd.Series):
            iterator: Iterable[Tuple[Any, Any]] = probability_series.items()
        elif isinstance(probability_series, dict):
            iterator = probability_series.items()
        elif isinstance(probability_series, (list, tuple, np.ndarray)):
            iterator = enumerate(probability_series, start=1)
        else:
            LOGGER.warning("无法识别的概率输出类型 %s，忽略。", type(probability_series))
            return {}
        normalized: Dict[str, float] = {}
        for idx, value in iterator:
            key = self._index_to_iso(last_date, idx)
            normalized[key] = float(value)
        return normalized

    def _index_to_iso(self, last_date: pd.Timestamp, idx: Any) -> str:
        if isinstance(idx, (int, np.integer)):
            step = int(idx)
            if step <= 0:
                LOGGER.warning("收到非正整数步长 %s，默认按 1 个交易日处理。", idx)
                step = 1
            target_date = (last_date + pd.tseries.offsets.BDay(step)).date()
        else:
            target_date = pd.Timestamp(idx).date()
        return target_date.isoformat()

    def evaluate(self, request: PredictionRequest, prediction: PredictionResult) -> List[EvaluationResult]:
        if not request.run_evaluation or not request.evaluation_anchor:
            return []
        history = self._prepare_history(request)
        anchor = request.evaluation_anchor
        evaluation: List[EvaluationResult] = []
        for horizon in request.horizons:
            _, future_returns = slice_history(history, anchor=anchor, horizon=horizon)
            horizon_predictions = prediction.horizon_returns.get(horizon)
            if not horizon_predictions:
                LOGGER.warning("缺少 %s 日预测结果，无法评估准确率。", horizon)
                evaluation.append(
                    EvaluationResult(
                        horizon_days=horizon,
                        accuracy=0.0,
                        total_cases=0,
                    )
                )
                continue
            predicted_direction = []
            real_direction = []
            for idx, real_return in future_returns.items():
                key = idx.date().isoformat()
                if key not in horizon_predictions:
                    LOGGER.warning(
                        "预测结果中缺少 %s 日对 %s 的数值，跳过该交易日。",
                        horizon,
                        key,
                    )
                    continue
                predicted_direction.append(horizon_predictions[key] >= 0)
                real_direction.append(real_return >= 0)
            total_cases = len(real_direction)
            if total_cases:
                accuracy = float(
                    sum(p == r for p, r in zip(predicted_direction, real_direction)) / total_cases
                )
            else:
                accuracy = 0.0
            evaluation.append(
                EvaluationResult(
                    horizon_days=horizon,
                    accuracy=accuracy,
                    total_cases=total_cases,
                )
            )
        return evaluation


__all__ = ["PredictionService"]
