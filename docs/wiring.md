# 接线方案：三部分输入、输出与衔接点

> 约定：本文件只写已核实的对照。源仓库的模块名、文件路径与数字均取自两个开源仓库的 README 与实际布局；凡是还没做的，一律列进 §5 缺口清单，不虚构。

## 1. 总览

```text
ANPR 过车记录（上游 plate1 / 下游 plate2，study_config.yaml 指定）
        │
        ▼
┌─────────────────────────┐
│ ANPR 预测                │  data_processing.py：事件匹配、可用性特征、轨迹对齐、完整周期切分
│ 5 分钟周期边界切分       │  forecast_models.py：快照 / 循环混合密度网络与训练
│ 概率预测 + 可靠性门控    │  probabilistic_metrics.py：概率评分、支撑修正、块重采样
└──────────┬──────────────┘  frozen_evaluation.py：冻结测试集一次性评测与服务 KPI
           │ 周期监测输出（预测区间 + 发布/回退决定）
           ▼
┌─────────────────────────┐
│ 编排 orchestrator        │  收事件、分发、汇总、记日志
│ pipeline.py              │  周期关闭时触发预测；每箱触发滤波更新
└──────────┬──────────────┘
           │ 点过程事件时间戳
           ▼
┌─────────────────────────┐
│ 唤醒滤波                 │  experiment/engine.cpp：C++ 滤波核 + Python 封装
│ 按 Δ 分箱在线滤波        │  experiment/frozen_params.json：5 方法 × 4 箱宽冻结配置
│ 越率判断（κ 区域）       │  experiment/theory_regions.json：200 cell 的 κ 与区域
└─────────────────────────┘  experiment/run_experiment.py：实验入口
```

## 2. ANPR 预测：输入 / 输出 / 衔接点

来源仓库：`availability-aware-anpr-forecasting`（开源，MIT）。TR-C 返修的 R2 专用文件（`r2_experiment_runner.py`、`gate_selectivity.py`）与投稿目录（`submit_trc/`）只留在私有仓库 `LSTM-MDN-git-ready`，不在接线范围内。

| 项 | 内容 |
|---|---|
| 输入 | 上游与下游过车记录，`study_config.yaml` 里的 `plate1_path` / `plate2_path` 指定，`camera_up` / `camera_down` 指定卡口；每表须含 `leave_time`（时间戳）、`vehicle_id`（仅用于上下游匹配）、`camera_id`、`turn_id`（研究过滤用值 `2`）；14 维可用性特征 `x_t`（完成率 `R_comp`、在途比 `rho_t`、均值、方差、时空编码） |
| 处理 | `data_processing.py` 做事件匹配、可用性特征、轨迹对齐与完整周期切分；`forecast_models.py` 提供快照 / 循环混合密度网络与训练代码；`probabilistic_metrics.py` 提供概率评分、支撑修正、块重采样；`experiment_runner.py` 跑开发阶段（prepare、stage-a/b、k-scan、fixed-references、trees、ap01/03/06、final-models、freeze） |
| 输出 | 每个 5 分钟周期的分位数预测与 90% 区间；门控决定：信息充裕则发布自适应区间，信息匮乏则回退至训练边际先验；服务级 KPI 由 `frozen_evaluation.py` 一次性评测 |
| 衔接点 | 编排层在周期关闭时调用 `predict(period)`（见 `src/anpr_forecast/interfaces.py`），拿到 `ForecastResult` + `GateDecision`；冻结测试集评测入口为 `frozen_evaluation.py`；接口检查可用合成数据（`examples/generate_synthetic_events.py`），无需原始记录 |
| 已核实基准 | 论文报告的基准（私有仓库 README §7；公开版 README 不含数字表，复现需授权数据）：最优模型 Snapshot Quantile GBDT，CRPS 8.364 s，覆盖率 0.902，平均宽度 58.4 s；门控保留 74.9% 周期，覆盖率 0.918，平均宽度 59.1 s；CPU 推断时延 < 5.5 ms。R3 返修更新过部分数字，引用前以最新 R3 包为准 |
| 环境 | Python 3.9，scikit-learn 1.6.1，PyTorch 2.7.1（公开版报告环境）；`docs/experiment_protocol.md` 为执行顺序与数据使用边界；测试用 `python -m unittest discover -s tests` |

## 3. 唤醒滤波：输入 / 输出 / 衔接点

来源仓库：`wake-up-overshoot`（开源，Apache-2.0；`results/` 里 Binance 衍生结果为 CC BY-NC-SA 4.0）。

| 项 | 内容 |
|---|---|
| 输入 | 事件时间戳序列；分箱宽度 Δ ∈ {10, 50, 250, 1000} ms；方法与参数取 `experiment/frozen_params.json`（5 方法 × 4 箱宽 = 20 组冻结配置）；越率区域取 `experiment/theory_regions.json`（crossing index κ，200 个合成 cell：73 越率区 / 92 不越区 / 35 过渡区） |
| 处理 | `experiment/build.py` 编译 `engine.cpp`（C++17）；`check_engine.py` 做 C++ 核与 NumPy/SciPy 参考实现的逐箱对照（19 项检查）；`run_experiment.py` 为实验入口（`--synthetic-only --workers 6` 只跑合成部分） |
| 输出 | 每箱预测速率；越率判断：恢复后的预测是否超过恢复速率（按 κ 区域）；合成实验结论 H1–H3 与真实数据结论 R1–R3 见 `results/results.json` |
| 衔接点 | 编排层按箱宽把事件分箱后调用 `update(state, events)`（见 `src/wakeup_filter/interfaces.py`），拿到 `FilterResult`（预测速率 + 越率标记 + 区域）；真实数据需另行下载 Binance aggTrades（`BINANCE_RAW`，默认 `../data/raw`），数据不随库分发 |
| 环境 | Python ≥ 3.10（numpy、scipy、pandas、matplotlib、psutil），C++17 编译器（`g++ -O2 -std=c++17 -static`） |

## 4. 编排：事件流向

事件分两种，到达时流向不同：

```text
事件 A：ANPR 过车记录（上游/下游卡口）
  → 缓存到当前 5 分钟周期 → 周期关闭时
  → anpr_forecast.predict(period) → gate 决定
  → 发布：区间 + 覆盖率/宽度 → 监测输出
  → 回退：边际先验 + “未发布”标记 → 监测输出

事件 B：点过程事件时间戳
  → 按 Δ 分箱 → wakeup_filter.update(state, bin)
  → 预测速率 + κ 区域查表 → 越率标记
  → 汇总进当前周期监测输出
```

编排层不做模型计算，只做三件事：路由、汇总、记日志。主循环骨架见 `src/orchestrator/pipeline.py`（`run_event_loop`，待实现）。

## 5. 缺口清单（仍需用户补齐）

| # | 缺口 | 说明 |
|---|---|---|
| 1 | 实时 ANPR 接入 | 现有输入是离线过车表（`study_config.yaml` 指定路径）；实时卡口流的接入方式、认证与脱敏边界未定 |
| 2 | 实时事件流接入 | 滤波的真实数据目前是离线 Binance aggTrades；监测用的实时事件源（哪条流、什么频率）未定 |
| 3 | 部署目标 | 本地 / Colab / 云 VM 未定；GPU/TPU 需求只在接真实模型时产生，骨架本身不需要 |
| 4 | 联合评估 | 两部分各自的评估都已核实（ANPR：CRPS/覆盖率/门控；滤波：H1–H3/R1–R3），但合起来作为一个监测应用的端到端评估口径未定 |
| 5 | 告警通道 | 越率标记与门控回退发生时通知谁、用什么通道，未定 |
| 6 | Kiro 额度 | 规格任务循环消耗 Kiro 额度；预算与上限未定，`agent` 型钩子默认关闭，见 `.kiro/hooks/` |
| 7 | 投稿目录隔离 | TR-C / SPL 稿件留在私有仓库，本仓库不放稿件；后续若开源仓库结构变化，需同步更新 §2 的模块对照 |

## 6. 引用核对

- ANPR 部分对照：`availability-aware-anpr-forecasting` README（2026-11-05 读取），模块清单、输入 schema、复现命令与隐私边界；数字基准引自私有仓库 `LSTM-MDN-git-ready` README §7（公开版不含数字表）。
- 滤波部分对照：`wake-up-overshoot` README（2026-11-05 读取），`experiment/` 布局与复现命令。
- Kiro 钩子格式对照：Kiro 官方文档 Hooks（v1 JSON，`version: "v1"`，`hooks[].trigger` / `matcher` / `action`），IDE 1.0 / CLI V3。
