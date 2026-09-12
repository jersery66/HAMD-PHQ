# 原始数据 → AI24 条件数据谱系（冻结说明）

## 谱系顺序

1. **原始/早期来源**：PDCH 临床对话与早期 HAMD 结果位于 `PDCH\PDCH` 和 `hamd_analysis/Analysis/Analysis_History`；DAIC-WOZ 原始 participant archive 位于 `DAIC-WOZ\压缩包`。
2. **处理后的数据层**：DAIC-WOZ 的 `processed_research` 保存 turns、question-answer pairs、labels、participant index、split 和早期 condition-long 文件；PDCH 经过清洗、拆句和标注形成临床对话层。
3. **AI24 条件输出**：`pdch_all_models_all_conditions_v2_20260802` 和 `v3_missing9_20260802` 保存 C01–C16 逐维度输出、C17–C24 独立事件输出和全量汇总。`v3_missing9` 是缺失值 9 语义更明确的历史版本。
4. **规范化分析输入**：`outputs/pdch_all_prompt_fields_corrected_20260807/04_评分维度明细.csv` 是当前 C03–C16 逐条评分分析使用的 canonical derived input；它不是原始数据，源文件保持不变。
5. **结果分析层**：Stage 2 多条件融合、H14/coverage、校正题总相关、直接 Joint Cross-AI 和参考版式工作簿均从上述规范化输入派生。

## C01–C24 的边界

- C01–C16：包含直接等级路径和逐条评分路径；只有 C03、C04、C07、C08、C11、C12、C15、C16 进入当前条目/结构层主分析。
- C17–C24：独立事件/探索性条件，不能与 C01–C16 的逐条评分结果直接合并排序。
- 历史 AI24 工作簿用于溯源和研究演变，不替代当前 canonical input 和冻结 Stage 2 结果。

## 冻结策略

- 小型 PDCH 原始/历史文件、DAIC processed layer 和 AI24 主工作簿以 ZIP 冻结，ZIP 哈希和成员清单在上级 `FREEZE_ARTIFACT_MANIFEST.csv`、`FREEZE_ZIP_MEMBERS.csv` 中记录。
- DAIC-WOZ 原始 190 个 participant archive 约 86 GB，只登记路径、文件数和大小，未复制到 C 盘；原始 archive 未修改。
- 任何 9、NA、空值和 schema-invalid 记录都保留其原始语义；HAMD14 gold=9 不能转成 0。

## 便捷访问

canonical 04_评分维度明细、02_统一结果索引、AI24 V3 三个主工作簿以及 DAIC processed 关键 CSV 已另存为未压缩文件，便于直接读取；完整谱系仍以 ZIP 和哈希清单为准。

