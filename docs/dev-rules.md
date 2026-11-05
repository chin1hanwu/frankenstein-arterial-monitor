# 开发守则

## 1. 接口先行

- 改实现之前，先改 `src/*/interfaces.py` 与 `docs/wiring.md`，保持三者一致。
- 新功能先写进 `.kiro/specs/arterial-monitoring/tasks.md` 再动手，不做规格外的开发。
- 数字只引用已核实来源（开源仓库 README、实验输出、论文）；R3 返修后的数字以最新 R3 包为准，不凭记忆写。

## 2. 不碰的东西

- 本仓库不放稿件、投稿目录与未发表内容；TR-C / SPL 稿件留在私有仓库。
- 不复制两个源仓库的实现代码；只通过 `config/local.yaml` 里的路径引用。
- 不把真实数据（ANPR 原始记录、Binance aggTrades）提交进仓库；数据目录与输出目录已在 `.gitignore` 里。
- 不向 Kiroween / Devpost 提交任何内容；积分申请状态与开发无关。

## 3. 数据与隐私

- ANPR 原始记录与元数据留在数据提供方，受隐私约束；公开版配置用通用卡口标识，接口检查用合成数据（`examples/generate_synthetic_events.py`）；复现论文数字需授权数据。
- 车牌哈希、车辆标识等只出现在本地数据目录，不进 git、不进日志。
- Binance 数据按源仓库 README 各自下载，不随库分发；衍生结果的 CC BY-NC-SA 4.0 说明保留。

## 4. 测试与复现

- 骨架自检：`python scripts/check_interfaces.py`（只依赖标准库），每次改接口后都跑。
- 两个源仓库各自的复现命令保持可用，不为本仓库改动它们；联合评估口径见 `docs/wiring.md §5` 缺口 4，定下来之前不宣称端到端指标。
- 周期切分严格按 5 分钟边界，不跨越，不用未来信息。

## 5. Kiro 使用

- 规格驱动：需求 → 设计 → 任务，三件套在 `.kiro/specs/arterial-monitoring/`。
- Steering（`.kiro/steering/`）是常驻守则，随手改要同步更新本文档。
- 钩子分两类：`command` 型不消耗额度，可默认开启；`agent` 型会开启新的 agent 循环、消耗额度，默认关闭，打开前先确认预算。
- 钩子只监听低频接缝（保存、任务边界），不在高频事件上挂 agent 动作，避免自触发循环。
