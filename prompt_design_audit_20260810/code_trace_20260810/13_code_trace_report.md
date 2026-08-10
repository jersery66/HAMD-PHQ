# PDCH C01-C16代码级提示词与实验条件追溯

> 本模块只追溯代码、运行manifest和固定提示词来源；不使用模型结果，不进行性能关联分析。

## 结论先行

- `9eval_main.py` 的 `CONDITIONS` 共解析到 24 条，C01-C16全部纳入。
- C01-C16的输入路径由 `DATA_PATHS` 和 `clean`/`C` 字段决定；固定提示词由 `build_system_prompt → build_condition_prompt` 组装。
- `PDCH_PROMPT_DOCX` 存在时，`word_prompt_templates.py` 在导入时用 `prompt_docx_loader.load_prompt_docx` 覆盖条件提示词；因此“代码生成”和“DOCX覆盖”被分开追溯。
- 观察到的运行manifest为 351 个（含历史/探针记录）；同一版本多来源记录 3 组，其中经主运行筛选和提示词hash比对后仍需复核 0 组。
- 六组理论pair的代码级提示词状态计数：{'clean_single_factor': 6, 'mostly_single_factor': 12}。即使提示词正文完全相同，清洗/规整/文本范围仍然可能通过输入路径发生操纵；不能把输入操纵误写成prompt文字操纵。

## 如何读主表

1. `01_condition_code_trace.csv`：先看每个条件的 `input_path_expression`、`input_code_key`、`prompt_builder_call` 和 `runtime_prompt_source`。
2. `03_prompt_source_comparison.csv`：只比较HAMD/PHQ不同提示词来源的正文，不解释为条件效应。
3. `04_pairwise_diff.csv`：六组pair的实际固定prompt diff；`mostly_single_factor`只表示输入描述文字变化，不把它当成新的心理机制。
4. `06_remaining_manual_review.csv`：只保留代码和提示词hash无法消除的主运行来源冲突或真实diff歧义；同内容复用和非主运行安全探针不进入人工审核。

## 研究边界

- `thinking_mode`不是C01-C16条件字典字段；它由`PDCH_ENABLE_THINKING`和模型名回退逻辑控制，已在主表单独记录。
- C03→C04、C01→C02等clean pair在固定prompt不变时，解释为输入清洗操纵；C03→C07、C01→C05等可能只改变输入类型描述，代码级上属于输入处理/descriptor变化。
- 不根据MAE、准确率、置信度或任何预测字段定义prompt特征；冻结表不含gold、prediction、MAE、NAE、accuracy、bias、F1。

## 输入工作簿完整性

- 文件：`E:\数据库\代码\Data\PDCH\实验\github_upload_20260806\PDCH_PHQ_HAMD_所有模型所有条件_提示词字段完整修正版_20260807.xlsx`
- 大小：125056024 bytes；ZIP头：True；SHA-256：`b3286e7dbb28dc40f218b9ae35f87da7307cf7a0b7cb7da49e042eea327284e2`
- 读取后SHA是否一致：`True`；扫描状态：`zip_xml_dimensions`

## 输出

- `01_condition_code_trace.csv`
- `02_prompt_version_provenance.csv`
- `03_prompt_source_comparison.csv`
- `04_pairwise_diff.csv`
- `05_prompt_feature_coding.csv`
- `06_remaining_manual_review.csv`
- `07_frozen_input.csv`
- `08_prompt_templates.csv`
- `09_source_files.csv`
- `10_run_contexts.csv`
- `11_workbook_summary.json`
- `12_code_trace_qa.json`
- `PDCH_PHQ_HAMD_代码级条件追溯_20260810.xlsx`（由这些CSV生成的可读总表）
