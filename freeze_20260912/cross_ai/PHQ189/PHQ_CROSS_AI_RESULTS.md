# PHQ-8 189人 pooled 跨 AI 维度异构结果

本分析将 189 人作为一个整体分析宇宙，用新的 10 repeats × 5 folds 外层 OOF，并在每个 outer training set 内用 5-fold inner validation 选择固定的 item-specific model + condition。它是 exploratory pooled analysis，不是 independent external validation，也不覆盖原 primary142/test47 结果。

## 结果

CrossAI routing 的 total MAE 为 3.328。最强的固定模型基线是 C03_GLM（3.254），WithinAI_GLM 为 3.160。
与 C03_GLM 比较，CrossAI 的 Δtotal MAE=0.074，95% CI [-0.058, 0.206]，q=0.2851，方向是变差。与 WithinAI_GLM 比较，Δ=0.168，q=0.0004，同样变差。
CrossAI 相比 C03_DeepSeek 和 C03_Qwen 的总分 MAE 分别下降 0.757 和 0.884，但 cancellation ratio 分别增加 0.135 和 0.156。
CrossAI item NAE=0.209，C03_GLM=0.195；CrossAI cancellation ratio=0.307，C03_GLM=0.278。

## 路由稳定性

CrossAI 每个条目的最高联合 route 选择频率为 0.30–0.68，没有条目达到 0.70。模型和 condition 都会随 outer fold 改变，说明跨 AI 异构现象存在，但当前数据下没有形成稳定可部署 mapping。

## 结论

189 人 pooled OOF 支持“不同 AI 在不同条目上表现不同”的现象，但不支持把跨 AI 维度异构宣布为整体优于 GLM 或固定 C03 的最终方案。当前最合理的表述是：跨 AI routing 是有信息基础的探索性候选，但在总分、条目真实性、误差抵消和路由稳定性之间没有同时胜出。

下一步若要做正式扩展，应先统一 HAMD/PHQ 模型版本，再在独立目录重新跑相同流程；当前结果保留为 all189 pooled exploratory evidence。
