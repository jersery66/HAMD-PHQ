# 折分设计索引

## 当前正式折分

- 外层：10 repeats × 5 folds，共 50 个 outer fold；每次重复中每个受试者只进入一次验证折。
- 内层：5-fold subject-grouped CV，只在 outer training 内选择 condition、策略或融合参数。
- `fold_assignments.csv`：PHQ primary142（142×10=1,420 行）与 HAMD99（99×10=990 行）合计 2,410 行。
- `fold_condition_maps.csv`：早期异构条件总分分析的每折 condition map。
- `outer_fold_strategy_maps.csv`：A/B/C 三策略每个 outer fold、条目的锁定映射。
- `outer_inner_fold_mae.csv`：三策略的 outer-training / inner-fold 选择指标。
- `locked_inner_fold_mae.csv`：锁定映射的 inner-fold 选择记录。

## 不同分析模块的折分范围

| 模块 | 外层对象 | 外层记录 | 内层选择 | 说明 |
|---|---|---:|---|---|
| Stage 2 多条件融合 | PHQ primary142、HAMD99 | 10×5 | 5-fold | PHQ test47 只做 secondary replication |
| 三策略 A/B/C | PHQ primary142、HAMD99 | 10×5 | 5-fold | 复用同一 `fold_assignments.csv` |
| PHQ Cross-AI 异构 | 全 189 人 pooled | 10×5 | 5-fold | exploratory，不使用 primary/test split |
| HAMD Cross-AI 异构 | 全 99 人 pooled | 10×5 | 5-fold | H14 gold=9 不可评估 |
| Direct Joint Cross-AI | PHQ189、HAMD99 | 10×5 | 5-fold（Conservative-C） | 每折每条目在 AI×condition 候选池中选路 |

## 老师问题的直接回答

上次不是 leave-one-out。正式主分析是“10 次重复的 5 折外层 OOF + 每个 outer training 内 5 折 inner CV”。因此每个受试者会在每次重复中作为一次未参与选择的验证对象，适合做受试者层面的配对 MAE 检验。

`fold_assignments.csv` 的 SHA-256：`d502c77e29c238e89f3b741f9ef05bc07ef503f115498d1e297e75cee6e96ad6`。
