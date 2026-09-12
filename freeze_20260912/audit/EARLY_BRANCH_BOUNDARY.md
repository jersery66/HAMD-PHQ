# Early PDCH workspace branch

本支线补回 2025-11 至 2026-04 的早期 PDCH/HAMD 研究产物。它们来自当前标准化 `实验/outputs` 之前的工作区，提示词、事件/句子粒度、模型版本、受试者范围和评价口径可能不同，因此只作为历史谱系、方法演变和补充材料，不能直接与当前 Stage 2、Cross-AI 或文章主结果合并。

## 已冻结

- `early_selected_results.zip`：选中的初始标注/数据表、早期 HAMD 提取与 checkpoint、事件/全文/清洗条件比较、句子级患者/维度结果、leave-one-out 聚合报告和图。
- `EARLY_SELECTED_ARTIFACTS_MANIFEST.csv`：ZIP 成员和源文件 SHA-256。
- `EARLY_WORKSPACE_INVENTORY.csv`：外部早期工作区逐文件清单，包含未复制文件的精确路径、大小和指针原因。
- `EARLY_BRANCH_VERIFICATION.md/.json`：2415 个 ZIP 成员、源文件哈希和 ZIP 完整性核验。

## 保留为指针的内容

大型或原始层没有重复塞入冻结包：`leave-one-out/results` 的逐患者相似度矩阵约 5.12 GB，`小句分析/HAMD_Results_分小句_Updated.xlsx` 约 696 MB，另有按患者原话、API response、backup 和噪声转换中间层。它们未删除，inventory 中标为 `pointer_only`。

本支线不是新的正式结果。任何早期表格进入论文前，都必须回到当前 canonical input、锁定折分和 H14/test47 边界重新核对。

## 本次统计

- 外部早期工作区文件数：6331；指针文件：3916；选中冻结：2415。
- 指针文件字节数：6756609150；选中源文件字节数：225362896；ZIP 字节数：100292143。
- 原始数据未修改；没有调用模型。


