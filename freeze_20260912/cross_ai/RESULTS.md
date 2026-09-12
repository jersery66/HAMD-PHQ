# PHQ + HAMD 直接 Joint 跨 AI 维度异构结果

本版按老师要求把每个完整的 AI×condition 结果作为同一候选池，在每个条目、每个 outer training fold 内直接选路；不拆 AI 内部过程、不训练机器学习、不调用 LLM。旧的两阶段 anchored 结果保留在 `CROSS_AI_JOINT_HAMD_PHQ_old_method_audit.csv`，不与本版混写。

## 先看结论

- **PHQ-8：189 人 pooled exploratory。** C03-GLM 的 total MAE 为 3.254。直接 Joint-A 为 3.376（相对 C03-GLM Δ=+0.122，q=0.0560）；Joint-B 为 3.520（Δ=+0.266，q=0.0002）；CrossAI-C03 为 3.556（Δ=+0.302，q=0.0001）；Conservative-C 为 3.547（Δ=+0.293，q=0.0001）。四种跨 AI 路线均没有在总分 MAE 上超过 C03-GLM；Joint-A 是最接近者，但点估计仍更差。
- PHQ 的机制是：CrossAI-C03 的 item_NAE 为 0.193，略低于 C03-GLM 的 0.195，但其 cancellation ratio 仅 0.215，低于 C03-GLM 的 0.278，所以总分绝对误差反而更高。不能只看条目 MAE 或只看总分 MAE。
- **HAMD-16 core：99 人，排除 H14 后作为干净主层；strict17 和 available 是敏感性层。** C03-GLM total MAE 为 3.515；CrossAI-C03 3.435，Joint-A 3.482，Joint-B 3.416，Conservative-C 3.373。点估计都略低于 C03-GLM，但相对 C03-GLM 的 paired q 分别为 0.659、0.884、0.631、0.464，区间均跨 0，不能称为稳定优势。strict17 中完整被试数随方法为 57–70，结论只能作敏感性解释。

## Cross-AI 定义与核对

`PHQ_CROSS_AI_JOINT_candidate_table.csv` 含 9,600 行，`HAMD_CROSS_AI_JOINT_candidate_table.csv` 含 20,400 行；每行是 outer fold × item × AI × condition 的完整候选，并保存 A rho、B item MAE、coverage、候选池标记和四种选中标记。PHQ 的全部 1,200 个 C03 行、HAMD 的全部 2,550 个 C03 行均被保留；独立 verifier 检查每个 fold×item 恰好一个选中路由。

- Joint-A：所有候选直接 argmax corrected item-total rho。
- Joint-B：所有候选直接 argmin item MAE。
- CrossAI-C03：condition 固定 C03，只跨 AI 选 item 负责人。
- Conservative-C：先以 CrossAI-C03 为锚点，只有 inner one-SE 外才切换。

旧 B 与直接 Joint-B 的同路率只有 **PHQ 0.578、HAMD 0.632**，因此旧 B 不是“所有 AI×condition 直接全局 argmin”的同一个定义；旧结果仍保留，但不能替代本版。

## 输出表与边界

- `CROSS_AI_JOINT_HAMD_PHQ_main_table.csv`：所有单 AI、C03、WithinAI A/B、CrossAI-C03、Joint-A/B、Conservative-C，保持中性展示。
- `CROSS_AI_JOINT_HAMD_PHQ_result_summary.csv`：读者直接使用的结果摘要表；primary 标出 PHQ189 和 HAMD16 core，HAMD available/strict 标为 sensitivity。
- `CROSS_AI_JOINT_HAMD_PHQ_primary_result_summary.csv`：只保留两个主层的精简结果表。
- `CROSS_AI_JOINT_HAMD_PHQ_result_headline.csv`：工作簿首页使用的窄版结果表，直接显示 total MAE、相对 C03-GLM 的 Δ/q、item NAE 和 cancellation。
- `CROSS_AI_JOINT_HAMD_PHQ_ladder.csv`：按 single-AI-C03 → single-AI-A/B → CrossAI-C03 → Joint-A/B → Conservative-C 排列的比较梯子。
- `CROSS_AI_JOINT_HAMD_PHQ_comparisons.csv`：逐量表、逐层 paired Δ、CI、p、q；不把 PHQ 与 HAMD 原始 MAE 合并。
- `CROSS_AI_JOINT_HAMD_PHQ_mechanism.csv`：逐条目 item MAE/NAE 与总分 coverage、cancellation、weighted kappa。
- `CROSS_AI_JOINT_HAMD_PHQ_routes.csv` 与 `candidate_table.csv`：路由和候选池审计。

PHQ189 pooled 结果已明确标为 exploratory；正式 primary142/test47 边界沿用既有正式包。HAMD H14 gold=9 按不可评估处理，AI prediction=9 不转为 0；HAMD24 未纳入。源文件哈希未变，原始数据未修改。
