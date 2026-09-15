# 老师要求的方案选择与重复五折外推包

## 一句话结论

按会议指定的“总分 MAE 合并标准化效应量最大”规则，A 排名第一（跨 PHQ/HAMD 的受试者数加权 Hedges g_z = -0.387；B = -0.346；C = -0.341），因此后续只检验 A。

PHQ-8 中，DeepSeek-V4-Pro 和 Qwen3.7-Max 的验证折总分 MAE 显著低于各自 C03；GLM-5.2 不改善。HAMD16-core 中三个 AI 均未达到稳定外推标准。所有六个模型×量表单元的条目 NAE 或误差抵消均未同步改善，因此论文只能把阳性结果写成“总分 MAE 改善”，不能写成“逐条评分更准确”。

## 为什么这样做

- A/B/C 先按同一个主要结局做选择：下游检验是 held-out 总分 MAE，所以上游也按总分 MAE 的合并标准化效应排名。
- PHQ 使用全 189 人，HAMD 使用全 99 人；HAMD H14 的 gold=9 是不可评估，正式结果使用 HAMD16-core。
- 复用冻结的 10 次重复×5 折。每个 AI、每个条目只用 outer-training 受试者选择 A 条件，再把映射原样用于 held-out fold。
- 同一受试者的 10 次 OOF 结果先取均值，再做配对 sign-flip permutation、participant bootstrap CI；paired t 和 Wilcoxon 只作敏感性检验。
- 每个量表的三个 AI 做 BH-FDR。50 个重叠折只描述稳定性，不作为 50 个独立研究。

## 先看哪些文件

1. `老师要求_A方案选择与重复五折外推结果.xlsx`：面向汇报的完整结果表。
2. `RESULTS.md`：方法、结果和主张边界。
3. `03_strategy_selection_summary.csv`：A/B/C 选择证据。
4. `09_A_primary_inference.csv`：六个量表×AI 单元的正式外推检验。
5. `14_interpretation_decision_table.csv`：每个 AI 可以说什么、下一步怎么处理。
6. `13_A_full_cohort_candidate_maps.csv`：未来新受试者可用的全队列候选映射；没有通过外推的模型明确标为保留 C03。
7. `independent_verification_report.json`：独立重算 23 项检查。
8. `saved_workbook_verification.json`：保存后的工作簿 6 项检查。

## 主张边界

这是重叠队列上的重复交叉验证，属于内部跨受试者泛化，不是独立外部验证。全队列候选映射只能在新的独立样本或新中心前瞻验证后，才能升级为应用规则。
