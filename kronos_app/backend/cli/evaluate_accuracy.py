"""命令行工具：运行 Kronos 预测并验证准确率阈值。"""
from __future__ import annotations

import argparse
import json
from datetime import date
from typing import Iterable, List

from ..schemas import PredictionRequest
from ..services.prediction_service import PredictionService


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="基于 Kronos 的准确率评估工具")
    parser.add_argument("ticker", help="A 股证券代码，例如 600519.SH")
    parser.add_argument(
        "--horizons",
        default="1,3,5,10",
        help="预测天数列表，逗号分隔，默认 1,3,5,10",
    )
    parser.add_argument(
        "--anchor",
        required=True,
        help="评估锚定日期（YYYY-MM-DD，不含当天），例如 2025-10-10",
    )
    parser.add_argument(
        "--min-accuracy",
        type=float,
        default=0.8,
        help="最低可接受的方向准确率，默认 0.8",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="若指定，将评估结果写入 JSON 文件",
    )
    return parser.parse_args(argv)


def _parse_horizons(raw: str) -> List[int]:
    values = [p.strip() for p in raw.split(",") if p.strip()]
    unique = sorted(set(int(v) for v in values))
    if not unique:
        raise ValueError("预测天数列表不能为空")
    return unique


def run_evaluation(args: argparse.Namespace) -> dict:
    horizons = _parse_horizons(args.horizons)
    anchor = date.fromisoformat(args.anchor)
    request = PredictionRequest(
        ticker=args.ticker,
        horizons=horizons,
        evaluation_anchor=anchor,
        run_evaluation=True,
    )
    service = PredictionService()
    prediction = service.predict(request)
    evaluation = service.evaluate(request, prediction)
    payload = {
        "ticker": args.ticker,
        "anchor": anchor.isoformat(),
        "horizons": horizons,
        "evaluation": [item.dict() for item in evaluation],
        "prediction": prediction.dict(),
    }
    return payload


def ensure_threshold(payload: dict, min_accuracy: float) -> None:
    failing = [item for item in payload["evaluation"] if item.get("total_cases", 0) and item["accuracy"] < min_accuracy]
    if failing:
        summary = ", ".join(
            f"{item['horizon_days']}日: {item['accuracy']:.2%}"
            for item in failing
        )
        raise SystemExit(f"准确率未达到阈值 {min_accuracy:.0%}，失败项: {summary}")


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    payload = run_evaluation(args)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)
    ensure_threshold(payload, args.min_accuracy)


if __name__ == "__main__":  # pragma: no cover - CLI 入口
    main()
