## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: validate
- Origin Date: 2026-09-15
- Verification Status: VERIFIED
- Version Label: teacher_B_supplement_generalization_v1

# B方案补充：全队列重复五折外推

## 定位

会议指定的总分 MAE 合并效应量排名为 A=-0.387、B=-0.346、C=-0.341，因此主分析选择 A。本包按用户要求补充 B，不能替换 A 的主结果。B 的既有优势是条目真实性证据更均衡，并出现唯一 Level2/test47 支持；本次结果检验的是这些优势能否在全队列外层折中保持。

## B怎么做

PHQ 使用全189人，HAMD使用全99人并排除H14，复用冻结的10次重复×5折。每个AI、每个条目只在outer-training中按原始条目MAE最小选择condition，并列时优先C03、再看item Spearman、coverage和固定条件顺序；映射原样应用到held-out fold。正式推断先在受试者内平均10次OOF，再做配对sign-flip permutation和participant bootstrap CI；paired t和Wilcoxon是敏感性检验，量表内三个AI做BH-FDR。

## B结果

- HAMD-17/GLM-5.2: B MAE=3.324, C03=3.515, Δ=-0.191, 95%CI [-0.567, +0.195], sign-flip q=0.4884, paired-t p=0.3309, fold improvement=70.0%; Δitem NAE=+0.0027, Δcancellation=+0.0209. 点估计改善但区间跨0或FDR未通过，不支持稳定泛化。
- HAMD-17/Kimi-K2.6: B MAE=3.970, C03=4.101, Δ=-0.131, 95%CI [-0.487, +0.241], sign-flip q=0.4884, paired-t p=0.4764, fold improvement=64.0%; Δitem NAE=+0.0080, Δcancellation=+0.0481. 点估计改善但区间跨0或FDR未通过，不支持稳定泛化。
- HAMD-17/Qwen3.7-Max: B MAE=3.336, C03=3.586, Δ=-0.249, 95%CI [-0.540, +0.054], sign-flip q=0.3087, paired-t p=0.1030, fold improvement=76.0%; Δitem NAE=+0.0100, Δcancellation=+0.0643. 点估计改善但区间跨0或FDR未通过，不支持稳定泛化。
- PHQ-8/DeepSeek-V4-Pro: B MAE=3.707, C03=4.085, Δ=-0.377, 95%CI [-0.560, -0.198], sign-flip q=0.0003, paired-t p=0.0001, fold improvement=94.0%; Δitem NAE=-0.0006, Δcancellation=+0.0731. 验证折总分MAE显著低于C03，支持当前队列内跨受试者泛化。
- PHQ-8/GLM-5.2: B MAE=3.243, C03=3.254, Δ=-0.011, 95%CI [-0.101, +0.084], sign-flip q=0.8181, paired-t p=0.8206, fold improvement=52.0%; Δitem NAE=+0.0070, Δcancellation=+0.0245. 点估计改善但区间跨0或FDR未通过，不支持稳定泛化。
- PHQ-8/Qwen3.7-Max: B MAE=3.738, C03=4.212, Δ=-0.474, 95%CI [-0.666, -0.294], sign-flip q=0.0003, paired-t p=0.0000, fold improvement=98.0%; Δitem NAE=-0.0035, Δcancellation=+0.0612. 验证折总分MAE显著低于C03，支持当前队列内跨受试者泛化。

## AI等权总体效应

- HAMD-17: AI-equal participant composite ΔMAE=-0.191, 95%CI [-0.398, +0.022], p=0.0839.
- PHQ-8: AI-equal participant composite ΔMAE=-0.287, 95%CI [-0.395, -0.181], p=0.0001.

## 解释边界

- HAMD-17/GLM-5.2: 不支持B相对C03的稳定外推；保留C03；B仅作阴性或探索性结果。
- HAMD-17/Kimi-K2.6: 不支持B相对C03的稳定外推；保留C03；B仅作阴性或探索性结果。
- HAMD-17/Qwen3.7-Max: 不支持B相对C03的稳定外推；保留C03；B仅作阴性或探索性结果。
- PHQ-8/DeepSeek-V4-Pro: 仅支持总分MAE改善；条目误差或抵消未改善；作为B总分优化候选；不得宣称条目更准，需外部样本验证。
- PHQ-8/GLM-5.2: 不支持B相对C03的稳定外推；保留C03；B仅作阴性或探索性结果。
- PHQ-8/Qwen3.7-Max: 仅支持总分MAE改善；条目误差或抵消未改善；作为B总分优化候选；不得宣称条目更准，需外部样本验证。

B与C03的比较仍是当前队列内内部跨受试者OOF，不是独立外部验证。B与A都不能因为总分MAE下降就宣称条目评分更准确；全队列候选映射只供未来独立样本前瞻验证。
