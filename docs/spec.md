# 项目规格：Frankenstein Arterial Monitor

## 1. 目标

做一个**实时干道监测应用**，把三件本来不兼容的东西缝合为一：

1. **ANPR 概率行程时间预测**：对一条 ANPR 卡口覆盖的城市干道，给出概率行程时间预测，并在信息不足时诚实地说“这次不发布”。
2. **显式高斯点过程唤醒滤波**：对事件流做在线滤波，并在长静默后事件恢复时判断预测是否越率（overshoot）。
3. **Kiro 多智能体编排**：用规格驱动（spec-driven）的方式开发，规格、开发守则与自动化钩子都记在 `/.kiro` 里。

一句话：监测对象是干道，监测手段是“预测 + 滤波”，开发方式是 Kiro 规格驱动。

## 2. 非目标

- 不做可直接部署的实时监测服务（骨架阶段不承诺）。
- 不重写、不复制两个源仓库的实现；只做接口骨架与接线。
- 不碰稿件投稿流程（TR-C / SPL 的投稿目录留在私有仓库）。
- 不向 Kiroween / Devpost 提交任何内容；积分申请状态与本仓库无关。

## 3. 三部分职责与接口契约

| 部分 | 职责 | 输入 | 输出 | 契约文件 |
|---|---|---|---|---|
| ANPR 预测 `src/anpr_forecast/` | 每个 5 分钟周期结束时，给出该周期的概率行程时间预测与发布决定 | 周期内可用性特征（14 维：完成率、在途比、均值、方差、时空编码） | 分位数预测 + 90% 区间 + 门控决定（发布 / 回退至边际先验） | `interfaces.py`、`docs/wiring.md §2` |
| 唤醒滤波 `src/wakeup_filter/` | 对事件时间戳流做在线滤波，分箱更新预测速率，标记越率 | 事件时间戳；分箱宽度 Δ ∈ {10, 50, 250, 1000} ms；滤波方法与冻结参数 | 每箱预测速率；越率判断（按 crossing index κ 划分的区域） | `interfaces.py`、`docs/wiring.md §3` |
| Kiro 编排 `src/orchestrator/` | 收事件、分发给两部分、汇总输出、管理配置与日志；驱动 Kiro 规格任务循环 | ANPR 过车记录、点过程事件、配置 | 周期监测输出（预测 + 门控 + 越率标记）、运行日志 | `interfaces.py`、`pipeline.py`、`docs/wiring.md §4` |

两个源仓库都是开源的：ANPR 预测用 `availability-aware-anpr-forecasting`（MIT），唤醒滤波用 `wake-up-overshoot`（Apache-2.0）。TR-C 返修（R2/R3）与投稿目录只留在私有仓库 `LSTM-MDN-git-ready`，不在接线范围内。

## 4. 数据模型

- **ANPR 过车记录**：上游卡口与下游卡口的过车记录（时间戳、车辆标识、卡口号、转向号），离线形态由 `study_config.yaml` 里的 `plate1_path` / `plate2_path` 指定；实时形态待接入（见缺口清单）。公开版用通用卡口标识，原始记录留在数据提供方。
- **周期**：严格按 5 分钟边界切分，不跨越边界，杜绝未来信息泄漏（公开版 `data_processing.py` 的完整周期切分协议）。
- **可用性特征**（14 维）：完成率 `R_comp`、在途比 `rho_t`、均值、方差、时空编码。特征构建见公开版 `data_processing.py`。
- **预测输出**：分位数预测、90% 区间、覆盖率与宽度；门控决定发布或回退。论文报告的基准（私有仓库 README §7；公开版 README 不含数字表，复现需授权数据）：门控保留 74.9% 的高置信周期，周期加权覆盖率 0.918，平均宽度 59.1 s，CPU 推断时延 < 5.5 ms。注意：TR-C R3 返修更新过部分数字，引用前请以最新 R3 包为准。
- **点过程事件**：时间戳序列；滤波按 Δ 分箱，方法与参数取 `frozen_params.json`（5 方法 × 4 箱宽 = 20 组冻结配置），越率区域由 crossing index κ 决定（`theory_regions.json`，200 个合成 cell）。
- **监测输出**：每个周期一条记录——周期、预测区间、门控决定、滤波越率标记。

## 5. 配置

见 `config/example.yaml`，复制为 `config/local.yaml` 后填写。配置只放路径与超参，不放任何密钥与真实数据。

- 两个开源仓库的本地路径（`anpr_repo`、`filter_repo`）
- 数据目录（`study_config.yaml` 的 `plate1_path` / `plate2_path`、`BINANCE_RAW` 的本地值）
- 周期长度（300 s）、滤波箱宽、分箱方法
- 门控阈值（发布覆盖率目标 0.90）

## 6. 运行方式（骨架阶段）

1. 离线复现优先：两个源仓库各自的复现命令保持可用（ANPR：`experiment_runner.py` / `frozen_evaluation.py`；滤波：`experiment/build.py` → `check_engine.py` → `run_experiment.py`）。
2. 骨架自检：`python scripts/check_interfaces.py`（只依赖标准库）。
3. 实时循环：见 `src/orchestrator/pipeline.py` 的 `run_event_loop` 骨架，按 `docs/wiring.md §4` 的事件流实现。

## 7. 验收标准（骨架完成即满足）

- [ ] 三部分接口骨架存在且自检通过。
- [ ] 接线方案写清每部分的输入、输出、衔接点与事件流向。
- [ ] `/.kiro` 含规格（requirements / design / tasks）、开发守则（steering）、自动化钩子（v1 JSON）。
- [ ] 缺口清单明确列出仍需用户补齐的项，不虚构已完成的功能。

## 8. 风险与合规

- ANPR 数据：原始记录与元数据留在数据提供方，受隐私约束；公开版配置用通用卡口标识，接口检查用合成数据（`examples/generate_synthetic_events.py`）；复现论文数字需授权数据。
- 点过程真实数据（Binance aggTrades）不随库分发，按源仓库 README 各自下载。
- 本仓库保持私有；未发表的稿件内容、投稿目录一律不放进来。
