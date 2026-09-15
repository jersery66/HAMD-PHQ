# B 方案补充外推包

主分析仍按 PHQ/HAMD 各自的整体总分 MAE 效应量选择 A。本目录按要求补充 B，不能替换 A 的主结果。

## B 的结果

- PHQ/DeepSeek：B 相对 C03 的 ΔMAE = −0.377，95%CI −0.560～−0.198，FDR q=0.0003，98% 验证折改善；但条目 NAE 仅轻微下降，抵消率增加。
- PHQ/Qwen：ΔMAE = −0.474，95%CI −0.666～−0.294，FDR q=0.0003，98% 验证折改善；条目 NAE 下降，抵消率增加。
- PHQ/GLM：不支持稳定改善。
- HAMD/GLM、Kimi、Qwen：点估计均下降，但置信区间跨 0，均不支持稳定外推。

B 在条目层面比 A 更均衡，但总分效应小于 A；它仍然不能被写成逐条评分更准确。当前结果是全队列内部重复交叉验证，不是独立外部验证。

## 文件

- `RESULTS.md`：补充结果和解释边界。
- `09_B_primary_inference.csv`：六个模型×量表单元的正式比较。
- `10_B_fold_effect_distribution.csv`：50 个 held-out 折的描述性分布。
- `13_B_full_cohort_candidate_maps.csv`：全队列 B 候选映射，仅供未来新样本前瞻验证。
- `老师要求_B方案外推结果.xlsx`：补充结果工作簿。
- `independent_verification_report.json`：独立重算审计。
