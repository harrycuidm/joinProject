# Kronos A股预测平台

本项目基于 [Kronos](https://github.com/shiyu-coder/Kronos) 模型，为中国 A 股提供中文界面的预测与验证服务。由于运行环境无法直接访问互联网，请在本地或具备网络的服务器上完成部署，并确保行情数据与模型文件来源真实可靠。

## 功能概览

- ✨ 输入任意 A 股代码与自定义天数（默认 1/3/5/10 天）获取未来每日涨跌幅预测；
- 📈 调用 Kronos 模型进行推理，展示预测涨跌幅及置信度；
- ✅ 支持以指定日期为锚点的历史回测，计算方向性准确率，目标 ≥80%；
- 🌐 前端采用纯中文界面，便于业务人员快速操作。

## 目录结构

```
kronos_app/
├── backend/           # FastAPI 服务，负责数据拉取、模型推理与评估
│   ├── config.py      # 环境变量配置
│   ├── main.py        # API 入口
│   └── services/      # 业务逻辑
├── frontend/          # 静态前端，直接使用浏览器访问
│   └── index.html
└── README.md
```

## 部署步骤

1. **克隆 Kronos 仓库**

   ```bash
   git clone https://github.com/shiyu-coder/Kronos
   ```

   将 Kronos 仓库置于与本项目同级的位置，或通过环境变量 `KRONOS_REPO` 指定路径。

2. **准备 Python 环境**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r Kronos/requirements.txt
   pip install fastapi uvicorn[standard] tushare akshare pandas numpy pydantic
   ```

   - **数据源**：通过 `KRONOS_DATA_SOURCE` 切换行情提供方：
     - `tushare`（默认）：使用 [Tushare Pro](https://tushare.pro)，需在环境变量或 `.env` 中配置 `TUSHARE_TOKEN`；
     - `akshare`：使用开源的 [AkShare](https://akshare.xyz) 数据接口；
     - `csv`：使用本地预下载的真实历史数据，需在 `KRONOS_CSV_PATH` 指定文件路径（要求包含 `ts_code`、`trade_date`、`close` 等列）。
   - **模型接口**：根据 Kronos 仓库提供的推理函数，设置 `KRONOS_PREDICT_FN`，格式为 `模块路径:函数名`，例如：

     ```bash
     export KRONOS_PREDICT_FN="inference.api:predict_returns"
     ```

     该函数需接受 `history`（`pd.DataFrame`）与 `horizon` 参数，并返回可迭代的涨跌幅预测结果。

3. **启动后端服务**

   ```bash
   uvicorn kronos_app.backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **访问前端界面**

   将 `kronos_app/frontend/index.html` 置于任意静态服务器下（或直接用浏览器打开），并确保浏览器可以访问上述 API 地址（默认 `http://localhost:8000/api`）。

   若 API 端口不同，可在部署时通过反向代理或设置全局变量 `window.API_BASE` 来覆盖默认地址。

## 历史验证流程

1. 在前端界面勾选“启用历史准确率评估”，并填写评估锚定日期（例如 2025-10-10）。
2. 后端会拉取锚定日前的行情数据用于预测，同时提取锚定日之后真实的每日涨跌幅。
3. 系统比较预测方向与真实方向，计算准确率并返回。若准确率未达到 80%，请检查：
   - 模型参数是否与 Kronos 官方发布一致；
   - 所选数据源是否配置正确、数据是否完备；
   - 是否需要为 Kronos 模型执行再训练或微调。

## 命令行准确率校验

为方便批量验证 80% 以上的方向准确率，可在后端虚拟环境中执行：

```bash
python -m kronos_app.backend.cli.evaluate_accuracy 600519.SH --anchor 2025-10-10 --horizons 1,3,5,10 --output kronos_eval.json
```

- 程序会在标准输出中打印结果；若任一预测天数的方向准确率低于 `--min-accuracy`（默认 0.8），命令将以非零状态码退出；
- `--output` 可选，用于保存包含预测值与评估详情的 JSON 文件，以便留存审计；
- 若需对多只股票或多时间点做验证，可结合 `xargs`/`GNU parallel` 等工具批量执行。

## 真实数据声明

- 所有预测与评估均依赖真实的 A 股交易数据，来源可选 Tushare Pro、AkShare 或经审核的本地历史行情文件；
- 本项目不内置任何模拟、演示数据；如需离线运行，请提前下载真实历史行情并在 `KRONOS_DATA_SOURCE=csv` 情况下指向对应文件。

## 常见问题

| 问题 | 解决方案 |
| ---- | -------- |
| 提示未找到 Kronos 仓库 | 确认 `KRONOS_REPO` 指向正确路径，例如 `export KRONOS_REPO=/path/to/Kronos` |
| 提示未设置 KRONOS_PREDICT_FN | 按照 Kronos 推理脚本设置对应的模块和函数 |
| Tushare 认证失败 | 检查 `TUSHARE_TOKEN` 是否正确，或在调用过于频繁时增加等待时间 |

## 免责声明

- 模型准确率受市场波动、训练数据与参数设置影响，80% 为目标指标，请结合评估结果审慎使用。
- 请遵守所在国家及地区的证券监管法规，合理使用预测结果。
