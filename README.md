# Frankenstein Arterial Monitor（骨架）

Kiroween 2026 Frankenstein 参赛项目的开工骨架：把三件本来不兼容的东西缝进一个实时干道监测应用——

1. **ANPR 概率行程时间预测**（开源仓库 `availability-aware-anpr-forecasting`，MIT）
2. **显式高斯点过程唤醒滤波**（开源仓库 `wake-up-overshoot`，Apache-2.0）
3. **Kiro 多智能体编排**（本仓库 `/.kiro`：规格、开发守则、自动化钩子）

> 状态：这是骨架，不是可运行的应用。实时数据接入、实时监测循环、联合评估都还没做，按 `docs/wiring.md` 里的缺口清单继续开发。
>
> 积分已获批（4,000 Kiro Credits，2026 年 11 月 6 日），须在 12 月 4 日前兑换；本仓库不向 Kiroween 或 Devpost 提交任何内容。
>
> 本仓库是私有的；两个源仓库都是开源的，接线对照以开源版为准。TR-C 返修（R2/R3）与投稿目录只留在私有仓库 `LSTM-MDN-git-ready`，不接线。

## 三部分速览

| 部分 | 来源 | 输入 | 输出 |
|---|---|---|---|
| ANPR 预测 | `availability-aware-anpr-forecasting`，开源版 | 5 分钟周期边界内的可用性特征（14 维） | 概率行程时间预测 + 可靠性门控决定 |
| 唤醒滤波 | `wake-up-overshoot`，`experiment/` | 事件时间戳，按 Δ 分箱 | 每箱预测速率 + 越率（overshoot）判断 |
| Kiro 编排 | 本仓库 `/.kiro` | 规格任务、代码变更、会话事件 | 按规格推进的开发循环与自动化检查 |

接线细节见 [docs/wiring.md](docs/wiring.md)；项目规格见 [docs/spec.md](docs/spec.md)；开发守则见 [docs/dev-rules.md](docs/dev-rules.md)。

## 目录

```text
frankenstein-arterial-monitor/
├── README.md
├── docs/
│   ├── spec.md          # 项目规格
│   ├── wiring.md        # 接线方案：输入 / 输出 / 衔接点 / 缺口
│   └── dev-rules.md     # 开发守则
├── .kiro/
│   ├── steering/        # 常驻开发守则（product / tech / structure）
│   ├── specs/
│   │   └── arterial-monitoring/   # 规格：requirements / design / tasks
│   └── hooks/           # 自动化钩子（v1 JSON）
├── src/
│   ├── anpr_forecast/   # ANPR 预测接口骨架（stdlib only）
│   ├── wakeup_filter/   # 唤醒滤波接口骨架（stdlib only）
│   └── orchestrator/    # 编排接口与主循环骨架
├── scripts/
│   └── check_interfaces.py   # 接口自检（无第三方依赖）
├── config/
│   └── example.yaml     # 配置示例，复制为 local.yaml 后填真实路径
└── requirements.txt     # 接入真实实现时才需要的依赖
```

## 开始

```sh
# 1. 把两个开源仓库 clone 到本仓库旁边（不复制代码，只引用路径）
git clone git@github.com:chin1hanwu/availability-aware-anpr-forecasting.git ../availability-aware-anpr-forecasting
git clone git@github.com:chin1hanwu/wake-up-overshoot.git ../wake-up-overshoot

# 2. 复制配置并填真实路径
cp config/example.yaml config/local.yaml

# 3. 自检接口骨架（只依赖标准库）
python scripts/check_interfaces.py

# 4. 在 Kiro 里打开本仓库，按 .kiro/specs/arterial-monitoring/tasks.md 推进
```

## 守则要点

- 接口先行：改实现之前先改 `src/*/interfaces.py` 与 `docs/wiring.md`，保持三者一致。
- 不把未发表的工作内容（稿件、未公开数据、投稿目录）放进本仓库；本仓库保持私有。
- ANPR 原始记录留在数据提供方，公开版只用通用卡口标识与合成数据做接口检查；点过程真实数据（Binance aggTrades）不随库分发，各自下载。
- 钩子说明：`command` 型钩子不消耗额度，`agent` 型钩子会开启新的 agent 循环，默认只开了一个且处于关闭状态（见 `.kiro/hooks/`）。
