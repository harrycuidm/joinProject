"""真实市场数据获取模块。"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

try:  # pragma: no cover - the stub is exercised indirectly during tests
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    from .. import pandas_stub as pd  # type: ignore

try:
    import tushare as ts
except ImportError:  # pragma: no cover - 仅在未安装 tushare 时执行
    ts = None  # type: ignore

try:  # pragma: no cover - 按需安装 akshare
    import akshare as ak
except ImportError:  # pragma: no cover - 未安装时跳过
    ak = None  # type: ignore

from ..config import get_settings

LOGGER = logging.getLogger(__name__)


def _ensure_pro_client():
    settings = get_settings()
    if ts is None:
        raise RuntimeError(
            "未安装 tushare，请运行 `pip install tushare` 并设置 TUSHARE_TOKEN 环境变量。"
        )
    if not settings.tushare_token:
        raise RuntimeError("未找到 TUSHARE_TOKEN，请在环境变量或 .env 文件中配置。")
    return ts.pro_api(settings.tushare_token)


def _ensure_akshare():
    if ak is None:
        raise RuntimeError(
            "未安装 akshare，请运行 `pip install akshare` 或切换到其它数据源。"
        )
    return ak


def normalize_symbol(symbol: str) -> str:
    """将输入代码转换为标准格式。"""

    symbol = symbol.strip().upper()
    if "." not in symbol:
        raise ValueError("证券代码需包含交易所后缀，例如 600519.SH")
    return symbol


def _symbol_for_akshare(symbol: str) -> str:
    code, exchange = symbol.split(".")
    prefix = "sh" if exchange == "SH" else "sz"
    return f"{prefix}{code}"


def _fetch_with_tushare(symbol: str, start_dt: date, end_dt: date) -> pd.DataFrame:
    pro = _ensure_pro_client()
    df = pro.daily(
        ts_code=symbol,
        start_date=start_dt.strftime("%Y%m%d"),
        end_date=end_dt.strftime("%Y%m%d"),
    )
    if df.empty:
        raise RuntimeError(f"未能从 tushare 获取 {symbol} 的行情数据")
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df = df.sort_values("trade_date").set_index("trade_date")
    return df


def _fetch_with_akshare(symbol: str, start_dt: date, end_dt: date) -> pd.DataFrame:
    module = _ensure_akshare()
    ak_symbol = _symbol_for_akshare(symbol)
    df = module.stock_zh_a_hist(
        symbol=ak_symbol,
        period="daily",
        start_date=start_dt.strftime("%Y%m%d"),
        end_date=end_dt.strftime("%Y%m%d"),
        adjust="qfq",
    )
    if df.empty:
        raise RuntimeError(f"未能从 akshare 获取 {symbol} 的行情数据")
    df = df.rename(
        columns={
            "日期": "trade_date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "vol",
            "成交额": "amount",
            "涨跌幅": "pct_chg",
        }
    )
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values("trade_date").set_index("trade_date")
    # 将涨跌幅标准化为与 tushare 一致的百分比
    if "pct_chg" in df.columns:
        df["pct_chg"] = df["pct_chg"].astype(float)
    return df


def _fetch_from_csv(symbol: str, start_dt: date, end_dt: date) -> pd.DataFrame:
    settings = get_settings()
    if not settings.csv_data_path:
        raise RuntimeError("KRONOS_CSV_PATH 未配置，无法使用 csv 数据源")
    path = Path(settings.csv_data_path)
    if not path.exists():
        raise RuntimeError(f"未找到 CSV 数据文件: {path}")
    df = pd.read_csv(path)
    if "trade_date" not in df.columns or "ts_code" not in df.columns:
        raise RuntimeError("CSV 数据文件需包含 ts_code 与 trade_date 列")
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    start_ts = pd.Timestamp(start_dt)
    end_ts = pd.Timestamp(end_dt)
    mask_symbol = df["ts_code"].str.upper() == symbol
    mask_range = df["trade_date"].between(start_ts, end_ts)
    subset = df.loc[mask_symbol & mask_range]
    if subset.empty:
        raise RuntimeError(f"CSV 数据文件中未找到 {symbol} 在指定时间范围内的行情")
    subset = subset.sort_values("trade_date").set_index("trade_date")
    return subset


def fetch_daily_bars(
    symbol: str,
    end_date: Optional[date] = None,
    lookback_days: int = 400,
) -> pd.DataFrame:
    """获取指定证券的日线行情。"""

    end_dt = end_date or date.today()
    start_dt = end_dt - timedelta(days=lookback_days * 2)
    settings = get_settings()
    normalized = normalize_symbol(symbol)
    if settings.data_source == "akshare":
        return _fetch_with_akshare(normalized, start_dt=start_dt, end_dt=end_dt)
    if settings.data_source == "csv":
        return _fetch_from_csv(normalized, start_dt=start_dt, end_dt=end_dt)
    return _fetch_with_tushare(normalized, start_dt=start_dt, end_dt=end_dt)


def slice_history(
    history: pd.DataFrame,
    anchor: date,
    horizon: int,
) -> tuple[pd.DataFrame, pd.Series]:
    """基于锚定日切分历史数据，返回训练窗口和目标收益。"""

    anchor_ts = pd.Timestamp(anchor)
    past = history.loc[:anchor_ts].iloc[:-1]
    future = history.loc[anchor_ts: anchor_ts + timedelta(days=horizon * 2)]
    if len(past) < 60 or future.empty:
        raise RuntimeError("历史数据不足以执行预测或评估")
    future_returns = future["close"].pct_change().dropna()
    return past, future_returns


__all__ = ["fetch_daily_bars", "slice_history", "normalize_symbol"]
