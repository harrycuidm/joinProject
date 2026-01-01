"""封装 Kronos 模型的预测接口。"""
from __future__ import annotations

import importlib
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List

try:  # pragma: no cover - stub used in tests
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    from .. import pandas_stub as pd  # type: ignore

from ..config import get_settings

LOGGER = logging.getLogger(__name__)


@dataclass
class KronosRunner:
    """Kronos 模型的封装。"""

    repo_root: Path
    predict_callable: Callable[..., Any]

    @classmethod
    def initialize(cls) -> "KronosRunner":
        settings = get_settings()
        repo_root = Path(settings.kronos_repo).resolve()
        if not repo_root.exists():
            raise RuntimeError(
                f"未找到 Kronos 仓库路径 {repo_root}，请先克隆 https://github.com/shiyu-coder/Kronos"
            )
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))

        dotted = settings.kronos_predict_callable
        if not dotted:
            raise RuntimeError(
                "请通过环境变量 KRONOS_PREDICT_FN 指定 Kronos 预测函数，例如 'inference.api:predict_returns'"
            )
        module_name, func_name = dotted.split(":", 1)
        module = importlib.import_module(module_name)
        predict_callable = getattr(module, func_name)
        return cls(repo_root=repo_root, predict_callable=predict_callable)

    def predict_returns(
        self,
        history: pd.DataFrame,
        horizons: Iterable[int],
        **kwargs: Any,
    ) -> Dict[int, Any]:
        """调用 Kronos 模型预测未来收益。"""

        LOGGER.info("调用 Kronos 模型，预测天数: %s", list(horizons))
        outputs: Dict[int, Any] = {}
        for horizon in horizons:
            result = self.predict_callable(history=history, horizon=horizon, **kwargs)
            outputs[int(horizon)] = result
        return outputs


__all__ = ["KronosRunner"]
