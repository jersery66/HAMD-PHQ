# 老师要求的跨受试者外层泛化检验

## 老师这次要检验什么

先在外层训练受试者中选择条件组合，再把这张组合原封不动地应用到外层未参与选择的验证受试者；在同一批验证受试者上与原始 C03 条件比较总分 MAE。

定义：

`ΔMAE = MAE(训练折学到的组合) − MAE(C03 原始条件)`

ΔMAE < 0 表示改善。显著性以受试者层面的配对差值为单位，重复外层预测先在受试者内平均，随后做 sign-flip permutation 和 bootstrap 95% CI；不能把 10 次重复乘以 5 折当成相互独立的受试者。

## 当前设计

- 外层：10 repeats × 5 folds，每个受试者每次重复只进入一次验证折，约 80% 训练、20% 验证。
- 内层：5-fold，仅在 outer training 内选择条件组合或融合参数。
- 原始条件：C03。
- PHQ：primary142 作为选择/外层 OOF；test47 只作为锁定映射的 secondary replication。
- HAMD：PDCH 标签 99 人；H14 gold=9 不可评估，HAMD-16 core 作为主要可比层。
- 这里把老师口头的 MAD 按当前项目统一口径记录为总分 MAE；item MAE、item NAE、coverage 和 cancellation 作为辅助证据。

## 结果解释

PHQ-8 的 Qwen3.7-Max-B 在外层 OOF 中总分 MAE 低于 C03，区间完全低于 0，并在 test47 secondary replication 中方向保持。该结果支持“在本研究队列内，训练集学到的条件组合可以迁移到未参与选择的受试者”这一总分层面的证据。

HAMD-17 的 B 策略点估计多数下降，但主要 HAMD-16 core 层的 q 值未达到 0.05，不能写成显著泛化改善。HAMD 的某些点估计改善伴随 coverage、条目误差或误差抵消问题，因此不能仅凭总分 MAE 下​​降宣称可部署。

三策略 Level 结果中，唯一达到 Level 2 的单元是 PHQ-8/Qwen3.7-Max/B；Level 3 为 0。Level 3 还要求映射稳定性和误差抵消条件，当前没有方法同时满足。

## 结论边界

这支持的是同一研究队列内的 cross-subject out-of-fold generalization evidence，不是独立外部验证，也不是临床效度、诊断效度或因果证明。
