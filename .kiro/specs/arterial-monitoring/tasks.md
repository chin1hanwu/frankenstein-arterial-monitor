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
  - [ ] 2.2 滤波：`experiment/build.py` → `check_engine.py` → `run_experiment.py --synthetic-only`——2026-11-07 云会话：`build.py` 静态链接失败（沙箱缺静态库且文件系统只读装不上）；同日跟进：动态编译成功、check_engine 可见输出全 PASS，合成实验跑 65 分钟仍无输出（输出缓冲或卡住未定），待 HW 决定继续等 / 停掉重跑 / 就此收尾；HW 11:37 决定继续等，晚点再看结果；12:46 定时复查与 12:52 同窗口重试均被 Kiro 登录页挡住（云端浏览器登录已过期），实验状态自 11:37 后未知，需 HW 重新登录后复查
- [ ] 3. 实现 `anpr_forecast.predict`：接 `forecast_models.py` 的模型接口，服务 KPI 见 `frozen_evaluation.py`
- [ ] 4. 实现 `wakeup_filter.update`：接 `engine.cpp` 的 Python 封装与 `frozen_params.json`
- [ ] 5. 实现 `orchestrator.pipeline.run_event_loop`：事件路由、周期关闭触发、监测输出汇总
- [ ] 6. 写端到端冒烟测试：用离线过车表 + 合成事件流跑一个完整周期
- [ ] 7. 定缺口清单的 7 项：实时 ANPR 接入、实时事件流、部署目标、联合评估口径、告警通道、Kiro 额度、投稿目录隔离复核
