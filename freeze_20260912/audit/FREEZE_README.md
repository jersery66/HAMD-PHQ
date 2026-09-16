# PDCH 冻结数据与结果包（初始 2026-09-11，更新 2026-09-15）

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
- `02_FROZEN_STAGE2/`：当前正式 Stage 2 多条件融合、H14、coverage、selective、test47、老师要求的跨受试者外层泛化检验和可直接读取的折分文件
- `03_FROZEN_CROSS_AI/`：最新直接 Joint、旧 anchored、合并表和参考版式工作簿
- `04_FROZEN_SUPPORTING/`：校正题总相关、条目总相关、误差抵消和 coverage 关键证据
- `05_REFERENCE_MATERIALS/`：参考工作簿、会议/PPT 材料和研究方向报告
- `06_ADDITIONAL_ANALYSES/`：补充冻结的 29 组高价值历史分析；完整成员索引见 `MISSING_ANALYSIS_BUNDLE_INDEX.csv`
- `07_DAIC_WOZ_BRANCH/`：DAIC-WOZ official142/C5/Fake-D/ASI/LIWC/AIDA 独立支线，不能与 PDCH HAMD/PHQ 条目主线混合
- `08_EARLY_PDCH_BRANCH/`：2025-11 至 2026-04 的早期 HAMD/PHQ 工作区、事件/句子级实验和 leave-one-out 历史结果；单独解释，不能并入当前主线
- `90_INVENTORY_POINTERS/`：全部 outputs 目录的清单和未复制目录指针

- `FREEZE_COMPLETENESS_AUDIT.csv` / `FREEZE_COMPLETENESS_AUDIT.md`：PDCH/实验\outputs 的 107 个输出目录逐一审计

冻结目录：`freeze_20260911`
当前冻结 artifact manifest 共 335 条；PDCH outputs 的既有完整性审计仍覆盖截至 2026-09-12 登记的 107 个目录，2026-09-15 新增的老师要求量表分开 A 主包、B 补充包和 A/B 完整总表已作为独立正式内部验证模块冻结。早期外部工作区另列 6331 个文件，其中 2415 个选中冻结、3916 个保留指针；DAIC-WOZ 支线另有独立目录和结果目录表。

## 证据等级

`formal_primary` 只能用于有 manifest、QA 和复现边界的模块；`exploratory_complete` 只能用于探索性描述；`pointer_only` 不进入主结果。完整主张边界见 `claim_boundary_matrix.csv`。






老师要求的跨受试者泛化包见 `02_FROZEN_STAGE2/CROSS_SUBJECT_GENERALIZATION/`：训练折选择条件组合，验证折与 C03 原始条件做受试者层面的 MAE 配对检验。


折分索引见 `02_FROZEN_STAGE2/FOLD_DESIGN_INDEX.md`；正式设计为 10 repeats × 5 outer folds，inner training-only 5-fold。`PHQ_05_core_oof_predictions.csv` 和 `HAMD_11_core16_oof_predictions.csv` 是可直接读取的外层 OOF 预测表。

## 2026-09-15 老师要求的聚焦外推分析

最终包见 `02_FROZEN_STAGE2/TEACHER_EFFECT_SIZE_GENERALIZATION_20260915/`，B 补充见 `02_FROZEN_STAGE2/TEACHER_B_SUPPLEMENT_GENERALIZATION_20260915/`。本轮先在 PHQ 和 HAMD 内分别按整体总分 MAE 效应量选择方案，再对主方案 A 做每个 AI 独立的 10 次重复×5 折外推检验；B 另行补充。

- PHQ 平均总分 MAE：A=-0.602、B=-0.292、C=-0.119；HAMD 平均总分 MAE：A=-0.409、B=-0.295、C=-0.145；两个量表分别均选择 A，不合并量表效应。
- PHQ-8：DeepSeek 与 Qwen 的验证折总分 MAE 显著改善；GLM 不改善。
- HAMD16-core：三个 AI 均未达到稳定外推标准。
- 六个模型×量表单元的条目 NAE 或误差抵消均未同步改善，因此阳性结果只支持总分 MAE 优化。
- 证据边界是当前队列内重复跨受试者 OOF，不是独立外部验证；全队列候选映射仅供未来新样本前瞻验证。

主工作簿：`02_FROZEN_STAGE2/TEACHER_EFFECT_SIZE_GENERALIZATION_SCALE_SPECIFIC_20260915/老师要求_A方案外推结果.xlsx`。分析核验 13 项、独立重算 23 项、保存后工作簿核验 6 项及外部逐页渲染均通过。

完整 A/B 对照总表：`02_FROZEN_STAGE2/TEACHER_A_B_COMPLETE_COMPARISON_20260915/A_B方案完整分析总表.xlsx`。该表把量表内 A/B/C 选择、A 主结果、B 补充、NAE、抵消和稳定性放在同一张可汇报工作簿中。

双语 v2 图见 `02_FROZEN_STAGE2/TEACHER_A_B_FIGURE_V2_20260916/`。v2 已取消重复嵌套排版，使用四个独立面板；按要求，图文件已从 GitHub 公开树删除，仅保留在本地冻结包。

