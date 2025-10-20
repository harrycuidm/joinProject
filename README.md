# Kronos 集成脚手架

本仓库提供了一个中文界面的 Kronos 集成示例，包含 FastAPI 后端与纯静态前端。后端会在运行时调用本地的 [Kronos](https://github.com/shiyu-coder/Kronos) 模型仓库，并依赖真实的 A 股交易数据来完成预测与历史准确率校验。

> ⚠️ 请注意：本仓库 **不** 内置任何模型权重或行情数据，所有预测与评估必须在具备真实 Kronos 模型与行情源的环境中执行，否则无法满足 80% 的准确率验收要求。

## 目录

- `kronos_app/backend/`：FastAPI 服务与命令行工具。
- `kronos_app/frontend/`：中文单页前端，直接在浏览器中打开即可使用。
- `tests/`：用于回归测试的单元测试，聚焦在接口契约与数据格式，不包含离线模型。

## 使用流程概览

1. 克隆 Kronos 官方仓库，并在环境变量 `KRONOS_REPO` 中指向该路径。
2. 依据 Kronos 仓库提供的推理脚本设置 `KRONOS_PREDICT_FN`，例如 `inference.api:predict_returns`。
3. 根据需要选择数据源 (`KRONOS_DATA_SOURCE=tushare/akshare/csv`)，并准备相应的真实日线行情数据。
4. 在本仓库根目录运行 `uvicorn kronos_app.backend.main:app --reload` 启动后端，使用 `kronos_app/frontend/index.html` 访问前端页面。
5. 使用 `python -m kronos_app.backend.cli.evaluate_accuracy <TICKER> --anchor <YYYY-MM-DD>` 触发历史评估，验证方向准确率 ≥ 80%。

## 测试

单元测试主要校验服务端在获得 Kronos 输出后对数据的解析与准确率计算逻辑：

```bash
pytest
```

> 由于测试通过猴子补丁替换了 Kronos 推理与行情数据，运行 `pytest` 并不能证明真实环境下的 80% 准确率，只能保证数据流正确。如果需要真实准确率，请在本地加载 Kronos 模型并对照真实行情自行验证。
