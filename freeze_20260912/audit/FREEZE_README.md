# PDCH 冻结数据与结果包（初始 2026-09-11，更新 2026-09-12）

这个目录是研究工作区的冻结快照索引。它不删除、不覆盖工作区原始文件。

## 冻结原则

- 物理冻结 canonical derived input、当前 Stage 2 结果、直接 Joint Cross-AI 结果、旧 anchored 结果、关键机制/coverage 结果和文章主线材料。
- 历史、失败、smoke、部分完成或重复输出全部登记在 `ALL_OUTPUT_DIRECTORIES_INVENTORY.csv`，但只保留指针，不把它们升级为文章主结果。
- 大型逐轮文件使用 ZIP 保存；ZIP 成员路径和原文件 SHA-256 在 `FREEZE_ARTIFACT_MANIFEST.csv` 中记录。
- HAMD H14 gold=9 保持不可评估；AI prediction=9 不转为 0。HAMD24、PHQ test47 和 PHQ189 pooled 的边界不混写。
- DAIC-WOZ 支线单独冻结并单独解释，不与 PDCH HAMD/PHQ 条目主线混合。

## 文章主线

请先读 `PAPER_MAINLINE_PLAN.md`。文章主线是：多条件信息可能互补，但可靠评分不能只寻找 winner，必须同时报告总分误差、条目真实性、误差抵消、coverage 和不确定性。

## 目录

- `00_RAW_LINEAGE/`：原始来源、DAIC processed layer、AI24 C01–C24 条件工作簿及 raw archive 指针
- `01_FROZEN_INPUT/`：canonical 输入字段与契约（大型数据以 ZIP 冻结）
- `02_FROZEN_STAGE2/`：当前正式 Stage 2 多条件融合、H14、coverage、selective、test47，以及老师要求的跨受试者外层泛化检验
- `03_FROZEN_CROSS_AI/`：最新直接 Joint、旧 anchored、合并表和参考版式工作簿
- `04_FROZEN_SUPPORTING/`：校正题总相关、条目总相关、误差抵消和 coverage 关键证据
- `05_REFERENCE_MATERIALS/`：参考工作簿、会议/PPT 材料和研究方向报告
- `06_ADDITIONAL_ANALYSES/`：补充冻结的 29 组高价值历史分析；完整成员索引见 `MISSING_ANALYSIS_BUNDLE_INDEX.csv`
- `07_DAIC_WOZ_BRANCH/`：DAIC-WOZ official142/C5/Fake-D/ASI/LIWC/AIDA 独立支线，不能与 PDCH HAMD/PHQ 条目主线混合
- `08_EARLY_PDCH_BRANCH/`：2025-11 至 2026-04 的早期 HAMD/PHQ 工作区、事件/句子级实验和 leave-one-out 历史结果；单独解释，不能并入当前主线
- `90_INVENTORY_POINTERS/`：全部 outputs 目录的清单和未复制目录指针

- `FREEZE_COMPLETENESS_AUDIT.csv` / `FREEZE_COMPLETENESS_AUDIT.md`：PDCH/实验\outputs 的 107 个输出目录逐一审计

冻结目录：`freeze_20260911`
当前冻结 artifact manifest 共 164 条；PDCH outputs 共 107 个目录，其中 19 个已在既有冻结中，29 个高价值历史/支持性目录已追加打包，59 个 smoke/失败/部分完成/重复或不适合进入结果的目录保留为指针。早期外部工作区另列 6331 个文件，其中 2415 个选中冻结、3916 个保留指针；DAIC-WOZ 支线另有独立目录和结果目录表。

## 证据等级

`formal_primary` 只能用于有 manifest、QA 和复现边界的模块；`exploratory_complete` 只能用于探索性描述；`pointer_only` 不进入主结果。完整主张边界见 `claim_boundary_matrix.csv`。






老师要求的跨受试者泛化包见 `02_FROZEN_STAGE2/CROSS_SUBJECT_GENERALIZATION/`：训练折选择条件组合，验证折与 C03 原始条件做受试者层面的 MAE 配对检验。
