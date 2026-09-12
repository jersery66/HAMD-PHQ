# PDCH 研究完整性审计与时间线

## 审计范围

这次复查把三个层面分开：

1. `PDCH/实验\outputs` 的 107 个标准化输出目录；
2. `PDCH` 下 2025-11 至 2026-04 的早期工作区；
3. `DAIC-WOZ` 的独立 DAIC-WOZ 支线。

它们不能因为都含有 HAMD/PHQ 或 AI 输出就直接合并。每一层的提示词、事件/句子粒度、模型版本、样本边界和评价口径要按各自文件中的 manifest 解释。

## 从最开始到现在的研究谱系

| 阶段 | 已发现的内容 | 当前冻结位置 | 文章地位 |
|---|---|---|---|
| 2025-11 至 2026-01 | PDCH 原始临床表、HAMD/PHQ 标签和早期数据准备 | `00_RAW_LINEAGE/`；早期支线 `08_EARLY_PDCH_BRANCH/` | 数据来源和历史谱系 |
| 2026-02 | HAMD 早期抽取、checkpoint、停止/恢复和转换结果 | `08_EARLY_PDCH_BRANCH/early_selected_results.zip` | 历史方法演变，不能直接当正式结果 |
| 2026-03 至 2026-04 | 全文/事件/清洗/未清洗评分、患者/医生/联合相似度、句子级维度分析、leave-one-out 相似度 | `08_EARLY_PDCH_BRANCH/`；5.12 GB 相似度矩阵等保留精确指针 | 历史探索和候选机制 |
| 2026-07 至 2026-08 | 24/99/189 样本、AI24 C01–C24 条件、字段契约、三模型/思考模式、题总相关、总分和条目误差、A/B/C 策略、coverage、H14、test47 | `00_RAW_LINEAGE/`、`01_FROZEN_INPUT/`、`02_FROZEN_STAGE2/`、`04_FROZEN_SUPPORTING/`、`06_ADDITIONAL_ANALYSES/` | 当前 PDCH 正式/探索性主线的谱系 |
| 2026-09-09 | PHQ189 和 HAMD99 完整 Cross-AI item-specific routing OOF | `03_FROZEN_CROSS_AI/PHQ189_CROSS_AI_HETEROGENEITY_20260909/`、`HAMD99_CROSS_AI_HETEROGENEITY_20260909/` | Cross-AI 异构的探索性证据，直接 Joint 的前置分析 |
| 2026-09-09 至 2026-09-11 | anchored、direct Joint、合并表和参考版式 37-sheet workbook | `03_FROZEN_CROSS_AI/` | 直接 Joint 是探索性补充，不替代 Stage 2 主结果 |
| 2026-08 至 2026-09 | 教师方案、决策链、汇报 PPT 和结果整理 | `05_REFERENCE_MATERIALS/`、`06_ADDITIONAL_ANALYSES/` | 组织和沟通材料，只有有 manifest/QA 的结果表可支撑数值主张 |
| 独立支线 | DAIC official142、TF-IDF/embedding/C5/Fake-D/ASI、LIWC/AIDA | `07_DAIC_WOZ_BRANCH/` | 单独项目支线，不能与 PDCH HAMD/PHQ 条目结果池化 |

## 本次复查确认并补回的缺口

- 先前漏掉的 PHQ189 / HAMD99 Cross-AI 完整 OOF 已按原目录全量冻结，并通过源哈希、折分、OOF 行数、candidate grid、weighted kappa、H14/coverage 和 `verification_report` 核验。
- 原先只有指针的历史/支持性分析，从 21 组扩充为 29 组，放入 `06_ADDITIONAL_ANALYSES/missing_high_value_analyses.zip`；成员和源文件哈希在 `MISSING_ANALYSIS_BUNDLE_INDEX.csv`。
- 早期外部工作区也补回：6331 个文件做了逐文件 inventory，2415 个结果/数据文件选入 `08_EARLY_PDCH_BRANCH/early_selected_results.zip`，其余 3916 个大矩阵、原话、API response、backup 或中间层保留精确指针。ZIP 成员验证通过。
- 当前冻结包共有 164 条 artifact manifest 记录，冻结验证 10/10 PASS；原始数据未修改，未新增 LLM 调用或机器学习分析。

## 仍然不复制的内容和理由

- `实验/outputs` 中的 59 个目录属于 smoke、失败、未完成、旧 prompt/internal CV、重复输出、原始提取层或超大中间层；它们在 `FREEZE_COMPLETENESS_AUDIT.csv` 中有路径和状态，不进入文章主结果。
- `leave-one-out/results` 的逐患者相似度矩阵约 5.12 GB，`小句分析/HAMD_Results_分小句_Updated.xlsx` 约 696 MB，未重复复制；指针在 `08_EARLY_PDCH_BRANCH/EARLY_WORKSPACE_INVENTORY.csv`。
- DAIC raw archive 约 86 GB，只保留指针；DAIC 结果包已单独冻结。

## 论文使用边界

当前可写的中心问题仍是：多条件/多 AI 输出是否在总分误差、条目真实性、误差抵消、可评估性和不确定性之间形成可复核的可靠评分路径。早期工作区和 DAIC 支线用于解释研究演变或提供独立背景，不能用来补强当前 PDCH 的临床有效性、诊断、安全、因果或普适 winner 主张。HAMD H14 gold=9 始终不可评估；test47 是 secondary replication，不是独立外部验证。
