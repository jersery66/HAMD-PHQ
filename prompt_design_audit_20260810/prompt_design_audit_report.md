# PDCH PHQ-8 / HAMD-17 提示词设计审计报告

## 1. 数据与范围

- 源结果工作簿：`PDCH_PHQ_HAMD_所有模型所有条件_提示词字段完整修正版_20260807.xlsx`；大小 `125056024` bytes。
- 源文件 SHA-256：`b3286e7dbb28dc40f218b9ae35f87da7307cf7a0b7cb7da49e042eea327284e2`；生成前后相同：`True`。
- 源工作簿：8 个sheet；观察到 168 个 dataset×model×mode 上下文。
- 固定提示词来自两个本地DOCX；未从GitHub下载、未修改125 MB源文件。

## 2. C01-C16 模板稳定性

- 9个观察上下文均有完整 C01-C16（每个16行）；pair审计共 54 行，即每个上下文6组预设pair。
- 唯一静态模板 28 个；同一 dataset×condition 未发现多个 template ID。
- HAMD metadata 中观察到的 prompt_version：word-2026-06-25; 正式使用提示词-2026-06-25。
- PHQ metadata 中观察到的 prompt_version：PHQ8-word-2026-06-27; word-2026-06-25。
- 版本标签不是prompt hash；同一量表出现多个版本时只记录为版本不确定/需人工核对，不能直接宣称不同模型或思考模式使用完全相同的实际请求文本。

## 3. 六组重点pair与实际文本差异

| pair | 状态计数 | 固定文本层面的观察 |
|---|---:|---|
| HAMD-17 C03→C04 | {'clean_single_factor': 6} | 固定文本相同（变化在运行时输入条件）；版本组合数=2 |
| PHQ-8 C03→C04 | {'clean_single_factor': 3} | 固定文本相同（变化在运行时输入条件）；版本组合数=2 |
| HAMD-17 C03→C07 | {'mostly_single_factor': 6} | 检测到1种固定文本差异；详见04_prompt_pairwise_diff.csv；版本组合数=2 |
| PHQ-8 C03→C07 | {'mostly_single_factor': 2, 'uncertain': 1} | 检测到1种固定文本差异；详见04_prompt_pairwise_diff.csv；版本组合数=2 |
| HAMD-17 C03→C11 | {'mostly_single_factor': 5, 'uncertain': 1} | 检测到1种固定文本差异；详见04_prompt_pairwise_diff.csv；版本组合数=3 |
| PHQ-8 C03→C11 | {'mostly_single_factor': 2, 'uncertain': 1} | 检测到1种固定文本差异；详见04_prompt_pairwise_diff.csv；版本组合数=3 |
| HAMD-17 C01→C02 | {'clean_single_factor': 6} | 固定文本相同（变化在运行时输入条件）；版本组合数=2 |
| PHQ-8 C01→C02 | {'uncertain': 2, 'clean_single_factor': 1} | 固定文本相同（变化在运行时输入条件）；版本组合数=2 |
| HAMD-17 C01→C05 | {'clean_single_factor': 6} | 检测到1种固定文本差异；详见04_prompt_pairwise_diff.csv；版本组合数=2 |
| PHQ-8 C01→C05 | {'mostly_single_factor': 3} | 检测到1种固定文本差异；详见04_prompt_pairwise_diff.csv；版本组合数=1 |
| HAMD-17 C01→C09 | {'clean_single_factor': 5, 'uncertain': 1} | 检测到1种固定文本差异；详见04_prompt_pairwise_diff.csv；版本组合数=3 |
| PHQ-8 C01→C09 | {'uncertain': 1, 'mostly_single_factor': 2} | 检测到1种固定文本差异；详见04_prompt_pairwise_diff.csv；版本组合数=2 |

状态解释：`clean_single_factor` 接近单因素；`mostly_single_factor` 需要人工抽查；`multi_component_change` 只能按提示词包解释；`not_comparable`/`uncertain` 不允许干净机制解释。运行版本缺失或不同会将pair降级为uncertain。

## 4. 冻结的提示词特征

- 05_prompt_feature_coding.csv：174 个上下文行；每个特征都带 value、原文证据、自动置信度和复核标记。
- 特征来自固定DOCX文本，不使用MAE、等级准确率、证据覆盖率或其他模型表现结果。
- 复杂度字段是描述变量；estimated_token_count为字符数/4的粗略估计，不是供应商tokenizer计费量。

## 5. 人工复核

- 待复核行数：161；其中低置信度/不确定特征和pair版本/单因素问题均已进入06_prompt_feature_manual_review.csv。
- reviewer_code、reviewer_note、resolved 保持空白，不替人工作结论。

## 6. 输出与停止

- 已生成8个审计CSV、数据质量问题表、编码规则表、结果索引、Excel总表和方法文档。
- 09_冻结分析输入.csv不含gold/prediction/MAE/NAE/correct/sensitivity/specificity/bias/F1等结果字段。
- 本阶段在提示词设计审计完成后停止；不自动开始任何prompt feature与模型性能的关联分析。
