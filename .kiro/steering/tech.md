---
inclusion: always
---

# Tech

## 语言与运行环境

- Python 3.10+。骨架本身只依赖标准库（`scripts/check_interfaces.py` 可直接跑）。
- 接入真实实现时才需要：PyTorch、lightgbm / xgboost、numpy、scipy、pandas、pyyaml、matplotlib、pytest（见 `requirements.txt`）；滤波核另需 C++17 编译器。公开版 ANPR 报告环境为 Python 3.9、scikit-learn 1.6.1、PyTorch 2.7.1。

## 两个源仓库（都是开源的，只引用，不复制）

- `availability-aware-anpr-forecasting`（MIT）：ANPR 预测。`data_processing.py`（事件匹配、可用性特征、轨迹对齐、完整周期切分）、`forecast_models.py`（快照 / 循环混合密度网络）、`probabilistic_metrics.py`（概率评分）、`experiment_runner.py`（开发阶段）、`frozen_evaluation.py`（冻结测试集评测与服务 KPI）、`scripts/benchmark_inference.py`。R2 专用文件与投稿目录只在私有仓库，不接线。
- `wake-up-overshoot`（Apache-2.0）：唤醒滤波。`experiment/`（`engine.cpp` + Python 封装、`frozen_params.json`、`theory_regions.json`、`run_experiment.py`）。

本地布局：两个源仓库 clone 到本仓库旁边，路径写在 `config/local.yaml`（由 `config/example.yaml` 复制）。

## 关键常量（不要硬编码第二份）

- ANPR 周期：300 s，严格按边界切分。
- 滤波箱宽 Δ ∈ {10, 50, 250, 1000} ms；冻结配置 5 方法 × 4 箱宽。
- 门控：发布覆盖率目标 0.90；信息匮乏时回退至边际先验。

## 测试

- 骨架自检：`python scripts/check_interfaces.py`。
- 源仓库复现命令保持原样可用；联合评估口径未定之前，不宣称端到端指标。
