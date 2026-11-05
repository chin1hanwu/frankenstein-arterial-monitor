# Design: 实时干道监测（Frankenstein 骨架）

## 架构

```text
事件源（待接入：实时 ANPR 流、实时事件流）
        │
        ▼
orchestrator.pipeline.run_event_loop
   ├── 周期边界 → anpr_forecast.predict(period) → gate 决定 → 监测输出
   └── 事件分箱 → wakeup_filter.update(state, bin) → 越率标记 → 监测输出
```

编排层只做路由、汇总、记日志；模型计算留在两部分各自的源仓库实现里，本仓库只保留接口骨架。

## 组件

### anpr_forecast（`src/anpr_forecast/`）

- `interfaces.py`：`AvailabilityFeatures`（14 维）、`ForecastRequest`、`ForecastResult`（分位数、90% 区间）、`GateDecision`（发布 / 回退）。
- 对照源仓库 `LSTM-MDN-git-ready`：`enhanced_data_processing.py`（特征与周期切分）、`revision_models.py`（SnapshotMDN / RecurrentMDN / Quantile GBDT）、`revision_metrics.py`（CRPS / NLL / PIT / Pinball）、`gate_selectivity.py`（门控）。
- 周期 300 s；环境变量 `LSTM_MDN_DATA_DIR`。

### wakeup_filter（`src/wakeup_filter/`）

- `interfaces.py`：`FilterConfig`（方法、箱宽 Δ、κ）、`BinUpdate`、`FilterState`、`FilterResult`（预测速率、越率标记、区域）。
- 对照源仓库 `wake-up-overshoot`：`experiment/engine.cpp`（C++ 滤波核）、`experiment/frozen_params.json`（20 组冻结配置）、`experiment/theory_regions.json`（κ 与 200 cell 区域）、`experiment/run_experiment.py`（入口）。
- 箱宽 Δ ∈ {10, 50, 250, 1000} ms；真实数据环境变量 `BINANCE_RAW`。

### orchestrator（`src/orchestrator/`）

- `interfaces.py`：`AppConfig`、`Event`（`anpr_observation` / `point_event`）、`MonitoringOutput`。
- `pipeline.py`：`run_event_loop` 骨架——事件路由、周期关闭触发、输出汇总。待实现。

## 数据流

见 `docs/wiring.md §4`。两种事件流向不同：ANPR 记录按周期汇总，周期关闭时触发预测；点过程事件按箱宽实时更新滤波。

## 配置

`config/example.yaml` → 复制为 `config/local.yaml`：源仓库路径、数据目录、周期、箱宽、门控阈值。不放密钥与真实数据。

## 测试策略

- 骨架：`scripts/check_interfaces.py`（标准库 only），接口改动后必跑。
- 源仓库：各自复现命令保持可用；联合评估口径未定，不宣称端到端指标。
