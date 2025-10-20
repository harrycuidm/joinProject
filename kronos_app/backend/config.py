"""应用配置。"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Literal, Optional

try:  # pragma: no cover - real dependency preferred in production
    from pydantic import BaseSettings, Field, validator  # type: ignore
except ImportError:  # pragma: no cover
    from .pydantic_stub import BaseSettings, Field, validator  # type: ignore


class Settings(BaseSettings):
    """读取环境变量的配置对象。"""

    tushare_token: str | None = Field(
        default=None,
        env="TUSHARE_TOKEN",
        description="用于获取真实交易数据的 Tushare Token。",
    )
    data_source: Literal["tushare", "akshare", "csv"] = Field(
        default="tushare",
        env="KRONOS_DATA_SOURCE",
        description="行情数据源，可选 tushare、akshare 或 csv。",
    )
    csv_data_path: Optional[str] = Field(
        default=None,
        env="KRONOS_CSV_PATH",
        description="当 data_source=csv 时使用的本地 CSV 文件路径。",
    )
    kronos_repo: str = Field(
        default="Kronos",
        env="KRONOS_REPO",
        description="Kronos 模型所在的相对路径。",
    )
    kronos_predict_callable: str = Field(
        default="",
        env="KRONOS_PREDICT_FN",
        description="指向 Kronos 预测函数的 '模块:函数' 定义。",
    )
    default_horizons: List[int] = Field(
        default_factory=lambda: [1, 3, 5, 10],
        description="默认预测天数列表。",
    )

    class Config:
        env_file = os.environ.get("KRONOS_APP_ENV", ".env")
        env_file_encoding = "utf-8"

    @validator("default_horizons", pre=True)
    def _sort_horizons(cls, value: List[int] | str) -> List[int]:  # noqa: D401
        """确保预测天数列表升序并移除重复。"""

        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            value = [int(p) for p in parts]
        unique = sorted(set(int(v) for v in value))
        return unique


@lru_cache()
def get_settings() -> Settings:
    """获取单例配置。"""

    return Settings()


__all__ = ["Settings", "get_settings"]
