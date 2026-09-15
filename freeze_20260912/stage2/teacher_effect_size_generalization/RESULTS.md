## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: validate
- Origin Date: 2026-09-15
- Verification Status: VERIFIED
- Version Label: teacher_effect_size_generalization_v2

# 老师要求的方案选择与外推性结果

## 确定方案

确定后续方案为 **A**。会议明确要求后续用验证折总分 MAE 与 C03 比较，因此方案选择也使用同一个主要结局：先在每个量表内把同一受试者的三个 AI 差值等权平均，再把 PHQ 与 HAMD 的配对标准化效应按有效受试者数合并。合并效应越负，代表总分 MAE 改善越大；Level、条目真实性、稳定性和 test47 结果作为解释与风险约束，不用事后加权分数改变主要结局。

- A: PHQ mean ΔMAE=-0.602; HAMD mean ΔMAE=-0.409; cross-scale weighted g_z=-0.387 (rank 1); Level1=3, Level2=0, stability pass=0, test47 support=0. 按会议指定的总分MAE效应量标准，两量表合并标准化效应绝对值最大；因此进入外推检验。
- B: PHQ mean ΔMAE=-0.292; HAMD mean ΔMAE=-0.295; cross-scale weighted g_z=-0.346 (rank 2); Level1=2, Level2=1, stability pass=1, test47 support=1. 条目真实性证据较完整且有Level2/test47支持，但会议指定的总分MAE合并效应小于A。
- C: PHQ mean ΔMAE=-0.119; HAMD mean ΔMAE=-0.145; cross-scale weighted g_z=-0.341 (rank 3); Level1=2, Level2=0, stability pass=3, test47 support=0. 稳定性较好，但总分MAE合并效应最弱，且没有Level2或test47支持。

A 的两量表合并标准化总分效应最大，所以严格按会议规则选择 A。B 是唯一出现 Level2 且得到 test47 支持的方案，这说明它在条目真实性上更均衡；但它的总分 MAE 合并效应小于 A，因此不进入本轮主外推检验。A 的代价是既有探索结果中经常伴随条目误差和误差抵消增加，所以即使后续总分 MAE 外推成立，也只能解释为“总分误差改善”，不能解释为“每个条目都更准”。

## 后续外推怎么做

PHQ 使用全部 189 人，HAMD 使用全部 99 人；HAMD 主分析排除金标准为 9、不可评估的 H14，使用 HAMD16-core。两者复用已经冻结的 10 次重复 × 5 折外层划分。每个 outer training 内，分别对每个 AI、每个条目选择“预测条目分数与扣除该条目后的量表总分”校正 Spearman 相关最高的 condition；该映射原样用于 held-out fold。验证受试者上的 A 与同一 AI 的 C03 做配对比较。正式检验为先将同一受试者 10 次 OOF 结果求均值，再做受试者层面的 sign-flip permutation 与 bootstrap CI；paired t-test 和 Wilcoxon 是敏感性检验。50 个 fold 的分布只用于稳定性描述，不作为 50 个相互独立研究。

## 每个 AI 的结果

- HAMD-17/GLM-5.2: A MAE=3.381, C03=3.515, Δ=-0.134, 95% CI [-0.561, +0.319], sign-flip q=0.5592, paired-t p=0.5519, fold improvement=64.0%. Δitem NAE=+0.0081, Δcancellation=+0.0422. 点估计改善但区间跨0或FDR未通过，不支持稳定泛化。
- HAMD-17/Kimi-K2.6: A MAE=3.696, C03=4.101, Δ=-0.405, 95% CI [-0.852, +0.047], sign-flip q=0.2397, paired-t p=0.0808, fold improvement=76.0%. Δitem NAE=+0.0223, Δcancellation=+0.1224. 点估计改善但区间跨0或FDR未通过，不支持稳定泛化。
- HAMD-17/Qwen3.7-Max: A MAE=3.456, C03=3.586, Δ=-0.130, 95% CI [-0.536, +0.287], sign-flip q=0.5592, paired-t p=0.5307, fold improvement=62.0%. Δitem NAE=+0.0182, Δcancellation=+0.0565. 点估计改善但区间跨0或FDR未通过，不支持稳定泛化。
- PHQ-8/DeepSeek-V4-Pro: A MAE=3.303, C03=4.085, Δ=-0.781, 95% CI [-1.048, -0.507], sign-flip q=0.0001, paired-t p=0.0000, fold improvement=98.0%. Δitem NAE=+0.0079, Δcancellation=+0.1535. 验证折总分MAE显著低于C03，支持当前队列内跨受试者泛化。
- PHQ-8/GLM-5.2: A MAE=3.253, C03=3.254, Δ=-0.001, 95% CI [-0.121, +0.124], sign-flip q=0.9986, paired-t p=0.9932, fold improvement=48.0%. Δitem NAE=+0.0064, Δcancellation=+0.0267. 点估计改善但区间跨0或FDR未通过，不支持稳定泛化。
- PHQ-8/Qwen3.7-Max: A MAE=3.590, C03=4.212, Δ=-0.622, 95% CI [-0.873, -0.384], sign-flip q=0.0001, paired-t p=0.0000, fold improvement=98.0%. Δitem NAE=+0.0032, Δcancellation=+0.0908. 验证折总分MAE显著低于C03，支持当前队列内跨受试者泛化。

## 跨 AI 总体效应

- HAMD-17: three-AI equal-weight participant composite ΔMAE=-0.223, 95% CI [-0.522, +0.074], p=0.1557.
- PHQ-8: three-AI equal-weight participant composite ΔMAE=-0.468, 95% CI [-0.640, -0.298], p=0.0001.

总体效应是同一受试者在三个 AI 上的 ΔMAE 等权平均，再在受试者层面推断。它不是把三个相关 AI 当成三个独立研究做传统元分析。

## 按 AI 的最终处理

- HAMD-17/GLM-5.2: 不支持A相对C03的稳定外推；保留C03；A仅作阴性或探索性结果。
- HAMD-17/Kimi-K2.6: 不支持A相对C03的稳定外推；保留C03；A仅作阴性或探索性结果。
- HAMD-17/Qwen3.7-Max: 不支持A相对C03的稳定外推；保留C03；A仅作阴性或探索性结果。
- PHQ-8/DeepSeek-V4-Pro: 仅支持总分MAE改善；条目误差或抵消未改善；作为总分优化候选；不得宣称条目更准，需外部样本验证。
- PHQ-8/GLM-5.2: 不支持A相对C03的稳定外推；保留C03；A仅作阴性或探索性结果。
- PHQ-8/Qwen3.7-Max: 仅支持总分MAE改善；条目误差或抵消未改善；作为总分优化候选；不得宣称条目更准，需外部样本验证。

已经另行生成各 AI 用全队列拟合的 A 条件映射，只用于未来新增受试者的前瞻候选。它们没有参与本报告的 OOF 效应估计；只有 PHQ/DeepSeek 和 PHQ/Qwen 的映射具有当前队列内总分外推支持，其他模型仍应保留 C03。所有候选映射都需要新的独立样本才能升级为部署规则。

## 结论

后续主线按会议规则围绕 A 展开。只有验证折 CI 完全低于 0 且 FDR q<0.05 的 AI，才能称为在当前队列内具有跨受试者泛化证据。点估计改善但区间跨 0 的 AI，只能称方向性结果。即使总分 MAE 显著，若 item NAE、条目绝对误差或抵消变差，结果也只能支持总分层面的优化。Cross-AI 混合路由已经表现更差，保留为补充分析，不再进入后续主路径。

## 统计风险检查

11/11 fallacy types checked。Simpson：按量表和 AI 分层并另报总体复合；ecological：推断单位是受试者；Berkson：临床/DAIC 队列选择限制外推范围；collider：未加入结果导出的协变量；base-rate：本分析不是诊断分类；regression-to-mean：不是极端组前后比较；survivorship：PHQ189 与 HAMD16-core 维持全样本；look-elsewhere：A/B/C 探索后按会议预先指定的总分效应量规则选择 A，并在每个量表内对三个 AI 做 FDR；forking paths：条件、折分和 A 的选择规则均在本轮外推前锁定，但策略探索和外推仍使用重叠受试者，因此这是内部验证；causation：只陈述预测误差，不作因果主张；reverse causality：不涉及时间方向因果。
