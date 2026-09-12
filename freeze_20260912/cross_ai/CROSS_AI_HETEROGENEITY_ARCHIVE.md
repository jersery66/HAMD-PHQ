# Cross-AI 维度异构完整冻结

本目录保留 2026-09-09 完成并通过验证的两组 item-specific model-condition routing OOF：

- `PHQ189_CROSS_AI_HETEROGENEITY_20260909/`：PHQ-8 全 189 人 pooled exploratory；10 repeats × 5 folds；模型为 DeepSeek/GLM/Qwen，条件 C03/C04/C07/C08/C11/C12/C15/C16。
- `HAMD99_CROSS_AI_HETEROGENEITY_20260909/`：HAMD-17 全 99 人 pooled exploratory；H14 gold=9 不可评估，HAMD24 排除；10 repeats × 5 folds；模型为 GLM/Kimi/Qwen，条件同上。

这两组结果是后续直接 Joint Cross-AI 包的前置分析谱系。它们支持“不同 AI 在不同条目上表现不同”的探索性现象，但不支持整体优于固定 C03 或 Within-AI 基线的最终结论；test47 仍不是独立外部验证。原始数据未修改，完整哈希见 `../..\FREEZE_ARTIFACT_MANIFEST.csv`。
