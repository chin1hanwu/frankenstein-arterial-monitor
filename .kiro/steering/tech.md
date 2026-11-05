---
inclusion: always
---

# Tech

## 语言与运行环境

- Python 3.10+。骨架本身只依赖标准库（`scripts/check_interfaces.py` 可直接跑）。
- 接入真实实现时才需要：PyTorch 1.12+、lightgbm / xgboost、numpy、scipy、pandas、pyyaml、matplotlib、pytest（见 `requirements.txt`）；滤波核另需 C++17 编译器。

## 两个源仓库（只引用，不复制）

- `LSTM-MDN-git-ready`：ANPR 预测。Layer 2 为当前主线（`revision_*.py`、`r2_experiment_runner.py`、`gate_selectivity.py`、`submit_trc/`）；Layer 0/1 是历史原型，不接线。
- `wake-up-overshoot`：唤醒滤波。`experiment/`（`engine.cpp` + Python 封装、`frozen_params.json`、`theory_regions.json`、`run_experiment.py`）。

本地布局：两个源仓库 clone 到本仓库旁边，路径写在 `config/local.yaml`（由 `config/example.yaml` 复制）。

## 关键常量（不要硬编码第二份）

- ANPR 周期：300 s，严格按边界切分。
- 滤波箱宽 Δ ∈ {10, 50, 250, 1000} ms；冻结配置 5 方法 × 4 箱宽。
- 门控：发布覆盖率目标 0.90；信息匮乏时回退至边际先验。

## 测试

- 骨架自检：`python scripts/check_interfaces.py`。
- 源仓库复现命令保持原样可用；联合评估口径未定之前，不宣称端到端指标。
