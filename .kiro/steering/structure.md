---
inclusion: always
---

# Structure

```text
frankenstein-arterial-monitor/
├── README.md
├── docs/            # 规格（spec.md）、接线方案（wiring.md）、开发守则（dev-rules.md）
├── .kiro/
│   ├── steering/    # 常驻守则：product / tech / structure
│   ├── specs/
│   │   └── arterial-monitoring/   # 规格三件套：requirements / design / tasks
│   └── hooks/       # 自动化钩子（v1 JSON）
├── src/
│   ├── anpr_forecast/   # ANPR 预测接口骨架
│   ├── wakeup_filter/   # 唤醒滤波接口骨架
│   └── orchestrator/    # 编排接口与主循环骨架
├── scripts/         # 自检与工具脚本（标准库 only）
└── config/          # example.yaml（提交）/ local.yaml（本地填写，不提交）
```

## 规则

- 接口先行：改实现之前先改 `src/*/interfaces.py` 与 `docs/wiring.md`。
- 新功能先写进 `.kiro/specs/arterial-monitoring/tasks.md` 再动手。
- 真实数据、输出产物、本地配置不进 git（见 `.gitignore`）。
- 稿件、投稿目录、未发表内容不放进本仓库。
- 数字只引用已核实来源；R3 返修后的数字以最新 R3 包为准。
