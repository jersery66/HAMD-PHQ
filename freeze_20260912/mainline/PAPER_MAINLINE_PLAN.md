# PDCH HAMD / PHQ 文章主线与写作方案（冻结版）

## 一句话主线

当同一心理症状在多个提示条件下产生不同的 AI 评分时，单纯寻找一个“最佳 condition”并不足以建立可靠量表评分路径；更合理的评价必须同时考察总分误差、条目真实性、可评估性、误差抵消和不确定性，并明确哪些改进只停留在内部探索层面。

## 建议标题

中文：**多条件大语言模型心理量表评分的可靠性评价：总分误差、条目真实性、可评估性与选择性人工复核**

英文工作标题：**Reliability evaluation of multi-condition large-language-model scoring for depression scales: total-score error, item validity, evaluability and selective human review**

## 核心研究问题

1. 不同提示条件是否对不同症状条目产生可重复的表现差异？
2. 条目级条件选择或多条件融合能否降低总分误差，同时保持条目真实性和可评估性？
3. 总分改善是否由条目误差下降驱动，还是由正负误差抵消造成？
4. 当 HAMD 的 H14 或多条件结果不可评估时，能否用 coverage/disagreement 建立研究性的人工复核路径？

## 中心论点

本文不应把贡献写成“某个模型或 condition 获胜”。最稳的论点是：**多条件信息确实包含潜在互补性，但其收益依赖量表、模型、条目和评价层；总分层改善不能自动转化为条目级真实性或临床可用性，因此可靠路径必须把评分、可评估性和不确定性共同纳入评价。**

## 证据层次

### 主结果层

- PHQ-8：primary142 是正式主分析边界，test47 是已接触后的 secondary replication；本次 PHQ189 pooled Cross-AI 结果明确标为 exploratory。
- HAMD：HAMD-17 strict/available 作为敏感性层，HAMD16 core（99 人，排除 H14）作为主要干净方法学层；H14 gold=9 永远不可评估。
- 主比较：C03 基线、既有 B/Mean/Median/Ridge/ElasticNet 融合路径、条目误差和被试层配对不确定性。

### 直接 Joint Cross-AI 层

- Joint-A：所有完整 AI×condition 直接按 corrected item-total rho 竞争。
- Joint-B：所有完整 AI×condition 直接按 item MAE 竞争。
- CrossAI-C03：condition 固定 C03，仅按条目跨 AI 选负责人。
- Conservative-C：以 CrossAI-C03 为锚点，只有 inner one-SE 外才切换。
- 结果定位：探索性补充。PHQ 没有超过 C03-GLM；HAMD16 点估计略低但没有稳定统计优势。旧 anchored B 与直接 Joint-B 不是同一方法。

## 推荐文章结构（IMRaD）

### 1. Introduction（约 800–1,000 字）

先提出量表评分的三个实际问题：条件改变会不会改变条目评分、总分是否掩盖条目错误、无效/不确定条目如何处理。研究空白不是“缺一个更大的模型”，而是缺少一套能把 accuracy、item-level validity、evaluability 和 uncertainty 放在同一评价框架中的方法。结尾给出四个研究问题和贡献边界。

### 2. Methods（约 1,200–1,500 字）

说明 DAIC-WOZ PHQ189、PDCH HAMD99、模型/条件、标签和 H14 规则。明确 C03、B/Mean/Median 等既有路径与直接 Joint Cross-AI 的不同定义。描述 outer 10×5 OOF、inner one-SE（仅 Conservative-C）、被试层配对比较、MAE/NAE/sum item AE/cancellation/coverage/weighted kappa，以及 FDR family。把 HAMD16 定义为 methodological core，不能替代 HAMD17。

### 3. Results（约 1,500–1,800 字）

#### 3.1 数据完整性与条件异质性

先报告 canonical input、候选条件和有效率。展示不同条目/模型的候选差异，但只称 descriptive heterogeneity，不把它写成通用 mapping。

#### 3.2 PHQ：总分融合的收益与条目层分离

以 primary142 的 Mean/B 为主结果，报告其相对 C03 的 total MAE、CI、p/q。随后报告 item NAE、sum item AE 和 cancellation，说明总分改善可能伴随条目层证据有限或抵消增加。test47 只放 secondary replication。

#### 3.3 HAMD：H14 可评估性和 HAMD16 core

先报告 strict17/available 的完整率和 H14 gold=9。再报告 HAMD16 core 的总分和条目结果，说明点估计下降不等于稳定优势。加入 H14 rescue、coverage 和 disagreement 结果，明确这些是可评估性/不确定性证据。

#### 3.4 直接 Joint Cross-AI 探索

报告候选池完整性、route stability、Joint-A/B/C03/Conservative-C 的总分结果。PHQ 的直接 Cross-AI 没有总分优势；HAMD16 只有方向性点估计，不能宣布 Cross-AI 方案优于单模型。此节的作用是回答老师提出的异构问题，而不是制造新的主结果。

### 4. Discussion（约 1,200–1,500 字）

第一段回答主问题：条件差异存在，但未形成稳定通用 winner。第二段解释为什么 total MAE 与 item NAE 会分离，误差抵消必须单独报告。第三段解释 H14 和 coverage 对临床量表评分的影响。第四段提出“有效条目自动评分 + disagreement/无效条目人工复核”的研究性路径。第五段集中写限制：不同数据集模型集合不完全相同、PHQ189 pooled exploratory、test47 非独立外部验证、无独立 HAMD 队列、人工 evidence 双评者审核未完成、没有临床决策安全性验证。

### 5. Conclusion（约 250–350 字）

结论只保留三句话：多条件信息具有潜在互补性；收益不能脱离条目真实性、抵消和可评估性解释；当前最可靠的产出是评价框架和研究性人工复核路径，而不是固定的通用评分 mapping。

## 建议主表与图

| 编号 | 内容 | 证据文件 |
|---|---|---|
| Table 1 | 数据集、队列、模型、条件、H14/test47 边界 | canonical input + Stage2 manifest |
| Table 2 | PHQ primary142 / HAMD16 core 主结果：C03、B/Mean、直接 Joint 路线 | Stage2 performance + direct Joint primary summary |
| Table 3 | total MAE、item NAE、sum item AE、cancellation、coverage | Stage2 mechanism + direct Joint mechanism |
| Table 4 | H14 gold=9、AI 无效率、rescue 和 selective coverage | Stage2 H14/coverage CSV |
| Figure 1 | 从多条件输出到可靠评分路径的分析框架 | workflow schematic |
| Figure 2 | PHQ total MAE 与 item/cancellation 分离 | PHQ performance/mechanism |
| Figure 3 | HAMD H14 可评估性与 coverage-rescue | HAMD H14/coverage |
| Figure 4 | 条目级 route stability 与 selective review 曲线 | direct Joint route stability + Stage2 selective |

## 结果写作中的固定用词

- 使用：`internal OOF evidence`、`secondary replication`、`methodological core`、`exploratory routing`、`conditional improvement`。
- 避免：`clinical validity`、`clinical safety`、`diagnostic accuracy`、`causal mechanism`、`universal winner`、`HAMD16 replaces HAMD17`。
- 所有数字必须带 `scale + cohort/layer + method + N + CI/q`，不能把 HAMD strict、HAMD16、available 或不同 FDR family 的数字合并。

## 真正值得继续的工作

1. 完成 2,000 行 evidence 双评者人工审核，之后再决定是否能写内容效度相关结论。
2. 为 HAMD selective prediction 补被试层 bootstrap CI、自动保留率和人工复核成本。
3. 如果文章要声称泛化或临床应用，再补独立 HAMD 队列和预注册外部验证。
4. 暂停新增模型、condition winner 规则和大规模海选；当前数据已经足以写一篇方法评价文章。

## 既有分析的文章归位

- AI24 C01-C24 工作簿：放在数据谱系和方法附录，说明从原始资料到规范化输入的形成过程；C17-C24 不进入逐条评分主结果。
- 多字段、深层规律和 PLOS-inspired 结构分析：作为探索性补充，用于解释 evidence、confidence、coherence 和结构层信号，不承担主效应结论。
- 教师方案、master、汇报工作簿和 PPT：作为结果组织与汇报材料，不能替代 CSV/manifest/OOF 证据。
- 早期 24 人、三模型模式、baseline-focused 和 joint-analysis：放在研究演变/补充材料，不与当前 PHQ primary142、HAMD99 或直接 Joint 结果池化。
- staged extraction、partial、schema-invalid 和 smoke 输出：放入限制与缺口，不作为完成结果。

这样可以保留你已经做过的全部工作，同时只让分析层、队列和证据等级匹配的结果进入主文。
