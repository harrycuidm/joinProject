"""Pydantic 数据模型。"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - prefer real pydantic when available
    from pydantic import BaseModel, Field, validator  # type: ignore
except ImportError:  # pragma: no cover
    from .pydantic_stub import BaseModel, Field, validator  # type: ignore


class PredictionRequest(BaseModel):
    """预测请求体。"""

    ticker: str = Field(..., description="证券代码，例如 600519.SH")
    horizons: List[int] = Field(default_factory=list, description="预测天数列表")
    evaluation_anchor: Optional[date] = Field(
        default=None,
        description="评估锚定日期（不含该日）。",
    )
    run_evaluation: bool = Field(
        default=False,
        description="是否基于锚定日期执行事后准确率评估。",
    )

    @validator("ticker")
    def _ticker_upper(cls, value: str) -> str:  # noqa: D401
        """标准化证券代码。"""

        value = value.strip().upper()
        if not value:
            raise ValueError("证券代码不能为空")
        if "." not in value:
            raise ValueError("证券代码需包含交易所后缀，例如 600519.SH")
        return value

    @validator("horizons", pre=True, always=True)
    def _ensure_horizons(cls, value):  # noqa: D401
        """确保存在预测天数。"""

        if not value:
            return []
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            value = [int(p) for p in parts]
        unique = sorted(set(int(v) for v in value))
        if not unique:
            raise ValueError("预测天数不能为空")
        return unique


class PredictionResult(BaseModel):
    """模型预测输出。"""

    ticker: str
    horizons: List[int]
    daily_changes: Dict[str, Dict[str, float]] = Field(
        description="日期 -> {\"return\": 涨跌幅, \"probability\": 概率}",
    )
    horizon_returns: Dict[int, Dict[str, float]] = Field(
        default_factory=dict,
        exclude=True,
        description="每个预测天数对应的日期->涨跌幅映射，仅用于后台准确率评估",
    )
    horizon_probabilities: Dict[int, Dict[str, float]] = Field(
        default_factory=dict,
        exclude=True,
        description="每个预测天数对应的日期->概率值映射，仅用于后台准确率评估",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    """准确率评估结果。"""

    horizon_days: int
    accuracy: float
    total_cases: int


class PredictionResponse(BaseModel):
    """综合响应。"""

    prediction: PredictionResult
    evaluation: List[EvaluationResult] = Field(default_factory=list)
