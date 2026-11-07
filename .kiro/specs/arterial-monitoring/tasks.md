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
- [x] 接线对照改成两个开源仓库（ANPR：`availability-aware-anpr-forecasting`；滤波：`wake-up-overshoot`）

## 下一步（按顺序）

- [ ] 1. 填 `config/local.yaml`：两个开源仓库的本地路径与数据目录
- [ ] 2. 跑通两个源仓库各自的复现命令，确认基线可用
  - [x] 2.1 ANPR：`experiment_runner.py prepare` 与 `frozen_evaluation.py`（接口检查可用 `examples/generate_synthetic_events.py` 的合成数据）——2026-11-07 云会话验证通过：合成数据生成 + 10 个单元测试全部通过
  - [x] 2.2 滤波：`experiment/build.py` → `check_engine.py` → `run_experiment.py --synthetic-only`——2026-11-07 云会话验证通过：`build.py` 静态链接失败（沙箱缺静态库且只读），改动态编译成功、check_engine 19 项全 PASS；合成实验跑完（results.json 已写 runs/reproduction/）：H1 73/73 全区域成立，H2 2/24（仅非越区、dt=0.001、L=300/1200），H3 10/10 全区域成立（均为 control cells）；real-data 阶段因 --synthetic-only 跳过；三仓库 git 均 clean。注：首轮前台运行在 30 分钟工具时限处被中断（已写 1,132/1,184 个任务文件），后从已有文件续跑完成；build_info.json 仍记旧的静态失败，属 stale
- [ ] 3. 实现 `anpr_forecast.predict`：接 `forecast_models.py` 的模型接口，服务 KPI 见 `frozen_evaluation.py`
- [ ] 4. 实现 `wakeup_filter.update`：接 `engine.cpp` 的 Python 封装与 `frozen_params.json`
- [ ] 5. 实现 `orchestrator.pipeline.run_event_loop`：事件路由、周期关闭触发、监测输出汇总
- [ ] 6. 写端到端冒烟测试：用离线过车表 + 合成事件流跑一个完整周期
- [ ] 7. 定缺口清单的 7 项：实时 ANPR 接入、实时事件流、部署目标、联合评估口径、告警通道、Kiro 额度、投稿目录隔离复核
