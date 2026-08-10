# PDCH PHQ-8 / HAMD-17 提示词设计审计方法

## 目的与停止边界

本模块回答的是“C01–C16（同时保留C17–C24的模板记录）实际使用了哪些固定提示词、条件之间改变了什么、这些提示词中有哪些可预先解释的设计成分”。它不是性能再分析模块。

本阶段在看任何性能关联前冻结提示词设计变量。因此本模块明确不计算，也不解释以下关系：

`提示词特征 → sensitivity / specificity / MAE / NAE / bias / F1 / evidence drift / 任何正确性指标`

这些结果只能在下一阶段以本文件中的 `08_prompt_analysis_frozen_input.csv` 为左表、经过预注册的结果表为右表时再做，且必须保留版本、量表、模型、思考模式、条件和样本范围。

## 输入来源

1. 结果工作簿：`PDCH_PHQ_HAMD_所有模型所有条件_提示词字段完整修正版_20260807.xlsx`。脚本以 `openpyxl` 只读模式逐行读取，读取前后均计算 SHA-256；不覆盖、不复制125 MB源文件。
2. HAMD固定提示词：本地 `hamd正式使用提示词.docx`。
3. PHQ固定提示词：本地 `PHQ8_prompt_set_3_nonconditional_24_conditions_English.docx`。
4. 条件定义：从运行脚本 `9eval_main.py` 的 `CONDITIONS` 字面量通过 AST 读取，不凭聊天记录手写条件。

结果工作簿本身是结果/字段汇总，不保存每一次请求的 system prompt 正文。因而固定提示词文本必须以本地 DOCX 为权威来源；字段名看起来像 prompt 的列不能被自动当成 prompt。

## 固定提示词与动态输入的边界

完整请求可概念化为：

```text
固定 system instruction + 固定评分/等级规则 + 固定输出要求 + 被试特异动态输入
```

本模块的 `full_static_prompt` 只包含 DOCX 中对应 C01–C24 的固定部分，不包含被试ID、访谈原文、事件内容、文件路径、模型输出、金标准或误差。模板 hash 只对固定文本计算。

## Prompt hash

### exact hash

`exact_sha256 = SHA256(UTF-8 原始固定提示词文本)`。

### normalized hash

仅进行以下无语义规范化：

- CRLF 与 CR 统一为 LF；
- 删除每行行尾空格；
- 删除首尾无意义空白；
- 连续空行压缩为一个空行。

不替换同义词、不改中文、不删除句子、不做大小写模糊化。模板ID按 normalized hash 的确定性排序生成，因此同一真实静态模板只保留一个 `PROMPT_######`。

## Excel 字段盘点

`01_prompt_field_inventory.csv` 对8个源sheet的每一列给出：sheet、字段名、实际内容推断角色、dtype、行数、非空数、缺失率、基于 SHA-1 值摘要的唯一值数和示例。

角色只按真实单元格内容判断：

- `design_metadata/key`：量表、模型、思考模式、条件、被试、事件和输入范围等设计元数据；
- `fixed_prompt_text_observed`：实际出现 `# Role/# Instruction/# Step/# End Goal/# Narrow` 等提示词结构标记；
- `dynamic_input_or_source_text`：输入/访谈文本类内容；
- `model_output/derived_analysis`：分数、等级、证据、理由、置信度、概率、误差和准确性等；
- `provenance_metadata`：路径、运行上下文和 metadata；
- `analysis_or_other`：无法由内容可靠归类。

本次审计如果源结果工作簿没有固定 prompt 正文，会明确记录为数据质量问题，不能靠列名猜测。

## 条件设计字典

`03_condition_design_dictionary.csv` 从 `9eval_main.py` 的条件字面量生成。字段包括：

- `pathway`：`direct_grade`（等级）或 `itemwise_score`（逐条评分）；
- `cleaned`：是否清洗；
- `structured`：是否规整；
- `text_scope`：全文、事件序列或独立事件；
- `baseline_condition`：等级路径 C01、评分路径 C03；
- `intended_pair`：六个预设配对；
- `thinking_mode`：明确说明它由运行元数据决定，不是C01–C16条件内的固定prompt因子。

六组配对固定为：C03→C04、C03→C07、C03→C11、C01→C02、C01→C05、C01→C09。

## Prompt 特征编码

`02_unique_prompt_templates.csv` 除 C01–C24 条件模板外，还保留两个本地 DOCX 中各自的3个非条件预处理模板。非条件模板在结果工作簿中没有逐次调用日志，因此其 `occurrence_n/subject_n=0` 只表示“源结果表没有逐次记录”，不表示“提示词未运行”。

`05_prompt_feature_coding.csv` 一行对应一个观察到的 `dataset × model × mode × condition × prompt_template_id`；另加 `shared front prompt` 行对两个量表的3个非条件模板进行提示词本身的编码。特征只从固定 prompt 原文编码，并为每个判断保留：

`feature_value`、`feature_evidence_quote`、`auto_confidence`、`review_required`。

编码内容包括证据要求、原文引用要求、评分锚点、否定处理、缺失信息规则、时间窗口、频率规则、推断权限、说话者限制、拒答权限、输出刚性、逐条推理、聚合要求、不确定性要求，以及字符数、行数、粗略 token 数、规则行数、instruction 行数和输出约束行数。

“未明确写出”不填常识性默认值：使用 `none/absent/unspecified/uncertain`，并在低置信度或不确定时进入人工复核表。

`estimated_token_count` 仅为 `ceil(字符数/4)` 的可重复粗略描述，不是供应商 tokenizer 的正式计费计数。

## Pairwise diff 与单因素判断

`04_prompt_pairwise_diff.csv` 对每个量表、观察到的模型、思考模式和六组pair做固定文本比较：

- `exact_same`：原始固定文本 SHA 是否相同；
- `normalized_same`：规范化文本 hash 是否相同；
- `unified_diff`、新增/删除行；
- 特征编码前后变化、未变化和意外变化；
- `single_factor_status`：`clean_single_factor`、`mostly_single_factor`、`multi_component_change`、`not_comparable`、`uncertain`；
- `interpretation_allowed`：`single_factor_interpretation`、`bundle_interpretation_only` 或 `no_clean_interpretation`。

固定 prompt 完全相同并不表示“prompt文字造成了效果”，它表示该pair的预期变化发生在运行时输入条件，而不是 system prompt 文字。若运行元数据的 prompt_version 不同或缺失，静态 DOCX 差分不足以证明实际请求相同，pair会降级为 `uncertain`。

## 稳定性与版本

源结果 metadata 中的 `metadata_prompt_version` 被逐条件保留到模板、pair审计和冻结输入。版本标签不是 prompt hash；同一量表出现多个版本只表示需要人工核对实际请求文本，不能直接宣称模型、思考模式或被试使用了相同模板。

## 人工复核

`06_prompt_feature_manual_review.csv` 仅包含：低置信度/不确定特征、pair不是干净单因素、提示词来源提取不确定、无法可靠拆分 static/dynamic、或运行版本不一致等问题。`reviewer_code`、`reviewer_note`、`resolved` 保留为空，等待人工确认，不擅自填结论。

## 冻结分析输入

`08_prompt_analysis_frozen_input.csv` 一行对应一个观察到的条件上下文，只保留：

- dataset、model、mode、condition；
- pathway、清洗、规整、文本范围和预设基线；
- prompt_template_id、prompt version、prompt feature；
- 静态文本复杂度；
- 被试数、源行数和结果覆盖状态等非性能质量元数据。

此表没有 gold score、prediction、MAE、NAE、correct、sensitivity、specificity、bias、F1，也没有任何输出证据/理由表现指标。它是下一阶段与结果表受控 join 的唯一输入。

## QA 门槛

运行结束必须通过：

1. 源工作簿前后 SHA-256 一致；
2. `prompt_template_id` 唯一且 hash 映射确定；
3. 所有 `uncertain`/low confidence 进入人工复核；
4. 六组 pair 数等于观察到的量表×模型×模式组合数×6；
5. 冻结输入字段名和内容不含结果变量；
6. Excel 只写值、不写公式，并扫描 formula error；
7. 输出索引记录每个CSV和Excel的 hash、行数和说明。

本阶段完成后停止，不自动开始任何性能关联分析。
