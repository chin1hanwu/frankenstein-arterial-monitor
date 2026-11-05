# Tasks: 实时干道监测（Frankenstein 骨架）

> 骨架阶段的任务只做到“可开工”。实时接入、部署与联合评估见 `docs/wiring.md §5` 缺口清单，另立任务。

## 骨架（已完成）

- [x] 仓库结构与 `/.kiro` 布局
- [x] 项目规格（`docs/spec.md`）
- [x] 接线方案（`docs/wiring.md`）
- [x] 开发守则（`docs/dev-rules.md` + steering）
- [x] 规格三件套（requirements / design / tasks）
- [x] 自动化钩子（v1 JSON，见 `.kiro/hooks/`）
- [x] 三部分接口骨架（`src/*/interfaces.py`）与自检脚本

## 下一步（按顺序）

- [ ] 1. 填 `config/local.yaml`：两个源仓库的本地路径与数据目录
- [ ] 2. 跑通两个源仓库各自的复现命令，确认基线可用
  - [ ] 2.1 ANPR：`revision_experiment_runner.py prepare` 与 `revision_test_runner.py`
  - [ ] 2.2 滤波：`experiment/build.py` → `check_engine.py` → `run_experiment.py --synthetic-only`
- [ ] 3. 实现 `anpr_forecast.predict`：接 `revision_models.py` 的模型接口与 `gate_selectivity.py` 的门控
- [ ] 4. 实现 `wakeup_filter.update`：接 `engine.cpp` 的 Python 封装与 `frozen_params.json`
- [ ] 5. 实现 `orchestrator.pipeline.run_event_loop`：事件路由、周期关闭触发、监测输出汇总
- [ ] 6. 写端到端冒烟测试：用离线 CSV + 合成事件流跑一个完整周期
- [ ] 7. 定缺口清单的 7 项：实时 ANPR 接入、实时事件流、部署目标、联合评估口径、告警通道、Kiro 额度、投稿目录隔离复核
