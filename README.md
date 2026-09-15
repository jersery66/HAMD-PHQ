# PDCH HAMD/PHQ 冻结结果公开版

这是本地完整冻结包 `pdch_freeze_20260911` 的可公开、可复核子集，更新至 2026-09-15。

## 内容

- `mainline/`：文章主线、证据地图、关键结果表和主张边界。
- `stage2/`：PHQ/HAMD 多条件融合、老师要求的跨受试者外层泛化摘要、关键 CSV、核验报告和结果 ZIP。
- `stage2/teacher_effect_size_generalization/`：按会议要求先用 A/B/C 合并总分效应量选出 A，再对每个 AI 做全 189/99 队列的重复五折外推结果、工作簿、图和审计代码。
- `cross_ai/`：PHQ189/HAMD99 Cross-AI 维度异构、直接 Joint、比较表和参考版式工作簿。
- `supporting/`：题总相关、点二列相关、误差抵消、coverage 和 HAMD16 支持性结果。
- `lineage/`：从原始层到 AI24 条件层的来源目录、数据摘要和哈希，不含原始临床/API 数据。
- `audit/`：冻结包验证、107 个 outputs 目录完整性审计、早期工作区时间线和 DAIC 支线边界。

## 2026-09-15 聚焦结果

会议指定的总分 MAE 合并标准化效应量排名为 A=-0.387、B=-0.346、C=-0.341，因此后续只检验 A。PHQ-8 的 DeepSeek-V4-Pro 与 Qwen3.7-Max 在 held-out 验证折上支持总分 MAE 改善；GLM-5.2 不支持。HAMD16-core 的三个 AI 均未达到稳定外推标准。条目误差或误差抵消未同步改善，阳性结果只能解释为总分 MAE 优化。

## 数据边界

仓库是公开仓库。本公开版不上传原始 JSON、患者原话、API response、原始金标准、约 86 GB DAIC archive、超大原始/中间 ZIP，也不上传超过 GitHub 常规单文件限制的本地冻结 ZIP。完整本地冻结包保留在作者本地，公开版中的相对路径、哈希和指针用于回溯。

HAMD H14 的 gold=9 保持不可评估，AI prediction=9 不转为 0；PHQ test47 是 held-out/secondary replication，不是独立外部验证。Cross-AI 与 Joint 结果属于探索性补充，不宣称临床有效性、诊断效度、因果机制或普适 winner。A 外推结果是当前队列内重复交叉验证，不是独立外部验证；全队列候选映射需要新样本前瞻确认。

本公开版没有新增模型调用或机器学习分析。
