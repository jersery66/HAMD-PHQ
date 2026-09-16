# Figure contract

Core conclusion: A is selected by within-scale total MAE, but internal generalization is model- and scale-dependent and does not imply item-level accuracy.
Figure archetype: quantitative grid
Target output: double-column scientific figure, 183 mm wide
Backend: Python / matplotlib only
Final size: 7.2 × 6.25 inches
Panel map:
  a: PHQ/HAMD 分开 / separate A/B/C selection by mean total-score MAE
  b: A and B held-out ΔMAE versus the same-AI C03 baseline
  c: fold-direction stability and median top-route frequency
  d: item NAE and cancellation trade-off
Evidence hierarchy:
  hero evidence: panel b
  validation evidence: panel c
  controls/robustness: panels a and d
Statistics needed: participant-level sign-flip permutation, bootstrap 95% CI, paired t/Wilcoxon sensitivity, BH-FDR within scale
Source data needed: frozen scale-selection, A/B comparison, primary inference and route-stability tables
Image-integrity notes: no raw clinical images; all plotted marks are source-table values; SVG text remains editable; all display labels are bilingual
Reviewer risk: do not pool PHQ/HAMD effects; do not interpret total-score gains as item validity or external clinical validation
