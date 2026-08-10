# C01–C16代码级条件追溯方法

## 目的

本阶段只确定实验实现和固定提示词来源，不把模型输出或金标准用于提示词定义，也不计算模型性能。

## 权威来源

1. `9eval_main.py`：AST读取 `CONDITIONS` 和 `DATA_PATHS`；同时读取 `get_output_dir_name`、`build_system_prompt`、`_get_enable_thinking` 的源代码行号。
2. `word_prompt_templates.py`：读取实际 `build_condition_prompt` 的代码构造结果。
3. `prompt_docx_loader.py` 和运行 manifest：确认 `PDCH_PROMPT_DOCX` 是否在运行时覆盖代码默认提示词。
4. 本地 HAMD/PHQ DOCX：按条件标题解析固定文本，并计算字节级 SHA-256、固定文本 exact hash 和 normalized hash。
5. 结果工作簿：只作存在性、XLSX文件头、大小和前后 SHA-256 完整性核验，不参与特征或性能关联。

## 条件追溯

每个 C01–C16 行同时保存：

- `C` 代码键和 `clean` 状态；
- `DATA_PATHS` 中的 `type`、`path/dir` 表达式和根变量（`RAW_DIR`/`BASE_DIR`）；
- `direct_grade` 或 `itemwise_score` 路径；
- `get_output_dir_name` 形成的实际目录名；
- `build_system_prompt → build_condition_prompt` 调用链；
- `PDCH_PROMPT_DOCX` 覆盖钩子；
- thinking 的环境变量控制，而不是把 thinking 错当成 C 条件。

## Prompt模板与hash

固定 prompt 是 DOCX 条件正文或代码 builder 返回的静态文本。动态访谈、被试 ID、事件内容、文件路径和模型输出不进入 prompt hash。normalized hash 只做 CRLF/CR→LF、删除行尾空格、首尾空白和连续空行压缩；不做同义词改写或语义合并。

`PROMPT_<normalized_sha256前12位>` 是可复现的模板 ID。相同 normalized hash 必须映射到同一个 ID。

## Prompt版本溯源

逐个扫描本地运行 manifest，记录 `prompt_version`、`prompt_docx`、运行模式、模型、条件范围和 source mode。若同一版本同时出现 `code_builder` 与 `docx_override`，先区分主运行与安全探针，再比较可获得的固定提示词 normalized hash；主运行只有在来源内容无法证明一致时才进入剩余人工复核。同内容复用本身不构成问题。

## Pairwise diff

对以下六组进行固定文本比较：

- C03→C04：清洗；C03→C07：规整；C03→C11：文本范围；
- C01→C02：清洗；C01→C05：规整；C01→C09：文本范围。

`clean_single_factor` 表示固定 prompt 完全不变，操纵发生在输入路径；`mostly_single_factor` 表示只有输入类型描述文字变化；`multi_component_change`、`not_comparable`、`uncertain` 只在确有实质变化或证据不足时使用。

## 特征冻结

特征只从固定 prompt 文本或代码返回值直接编码，并保留 `feature_evidence_quote` 与 `auto_confidence`。当前保留证据要求、评分锚点、否定/缺失规则、时间/频率、推断许可、说话者限制、拒答、输出刚性、逐条推理、聚合、置信度/概率和静态复杂度等变量。

`07_frozen_input.csv` 只包含设计变量、prompt特征、复杂度和来源质量字段；禁止 gold、prediction、MAE、NAE、accuracy、bias、F1 等结果变量。

## 人工复核边界

`06_remaining_manual_review.csv` 仅保留：主运行中同一版本多个来源且固定内容无法证明一致、真实 pair diff 歧义或源文件解析不确定。非主运行安全探针、同内容提示词复用不进入人工审核；原先自动生成的161条语义分类表不作为本阶段工作负担。

## QA

程序核验：C01–C16覆盖、模板 hash→ID唯一、pair主键唯一、冻结表无结果字段、源工作簿前后 SHA 不变、DOCX/代码源文件存在。`PASS_WITH_REVIEW` 只表示仍有少量主运行来源冲突；若无未解决复核行则为`PASS`。这不表示源数据或条件解析失败。
