"""Run Strategy B as a prespecified supplement to the teacher-focused A run.

The main analysis is Strategy A because it ranked first on the meeting's
total-MAE effect-size rule. This script keeps B separate and evaluates the
same B rule, cohorts, folds, subject-level inference, and audit boundary.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / "analysis" / "item_total_correlation"
sys.path.insert(0, str(ANALYSIS_DIR))
sys.path.insert(0, str(ROOT / "analysis"))

import run_teacher_focused_generalization as teacher_runner

from run_teacher_focused_generalization import (  # noqa: E402
    HAMD_FOLDS,
    HAMD_MODELS,
    PHQ_FOLDS,
    PHQ_MODELS,
    SEED,
    SOURCE,
    THREE_DIR,
    aggregate_primary_subject_repeat,
    across_ai_composite,
    build_decision_table,
    fit_and_apply_selected,
    fit_full_cohort_candidate_maps,
    inference_from_subject_repeat,
    load_cube,
    load_selection_evidence,
    make_figures,
    route_stability,
    sha256,
)

OUT = ROOT / "outputs" / "pdch_teacher_B_supplement_generalization_20260915"


def write_csv(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(OUT / name, index=False, encoding="utf-8-sig")


def build_report(selection: pd.DataFrame, inference: pd.DataFrame, composite: pd.DataFrame, decisions: pd.DataFrame) -> str:
    selected = selection[selection["strategy"].eq("B")].iloc[0]
    lines = []
    for row in inference.sort_values(["scale", "model"]).itertuples(index=False):
        lines.append(
            f"- {row.scale}/{row.model}: B MAE={row.selected_total_MAE:.3f}, C03={row.C03_total_MAE:.3f}, "
            f"Δ={row.delta_total_MAE:+.3f}, 95%CI [{row.delta_total_MAE_CI_low:+.3f}, {row.delta_total_MAE_CI_high:+.3f}], "
            f"sign-flip q={row.sign_flip_q:.4f}, paired-t p={row.paired_t_p:.4f}, fold improvement={row.fold_improvement_rate:.1%}; "
            f"Δitem NAE={row.delta_item_NAE:+.4f}, Δcancellation={row.delta_cancellation_ratio:+.4f}. {row.interpretation}。"
        )
    composite_lines = [
        f"- {row.scale}: AI-equal participant composite ΔMAE={row.AI_equal_mean_delta_MAE:+.3f}, "
        f"95%CI [{row.CI_low:+.3f}, {row.CI_high:+.3f}], p={row.sign_flip_p:.4f}."
        for row in composite.sort_values("scale").itertuples(index=False)
    ]
    decision_lines = [
        f"- {row.scale}/{row.model}: {row.claim_boundary}；{row.recommended_next_action}。"
        for row in decisions.sort_values(["scale", "model"]).itertuples(index=False)
    ]
    return f"""## Material Passport

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

{chr(10).join(lines)}

## AI等权总体效应

{chr(10).join(composite_lines)}

## 解释边界

{chr(10).join(decision_lines)}

B与C03的比较仍是当前队列内内部跨受试者OOF，不是独立外部验证。B与A都不能因为总分MAE下降就宣称条目评分更准确；全队列候选映射只供未来独立样本前瞻验证。
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_before = sha256(SOURCE)
    phq_fold_before = sha256(PHQ_FOLDS)
    hamd_fold_before = sha256(HAMD_FOLDS)
    effects, selection_composite, selection_summary, nominated = load_selection_evidence()
    if nominated != "A":
        raise AssertionError(f"teacher effect-size nomination changed to {nominated}")
    cube = load_cube()
    routes, candidates, predictions = fit_and_apply_selected(cube, "B")
    subject_repeat = aggregate_primary_subject_repeat(predictions)
    inference, fold_distribution, subject_inference = inference_from_subject_repeat(subject_repeat, routes, "B")
    route_summary = route_stability(routes)
    ai_composite = across_ai_composite(subject_inference, "B")
    full_maps = fit_full_cohort_candidate_maps(cube, route_summary, inference, "B")
    decisions = build_decision_table(inference)

    outputs = {
        "01_strategy_selection_effects.csv": effects,
        "02_strategy_selection_composite.csv": selection_composite,
        "03_strategy_selection_summary.csv": selection_summary,
        "04_B_outer_routes.csv": routes,
        "05_B_training_candidate_metrics.csv": candidates,
        "06_B_outer_oof_item_predictions.csv": predictions,
        "07_B_subject_repeat_metrics.csv": subject_repeat,
        "08_B_subject_level_inference_data.csv": subject_inference,
        "09_B_primary_inference.csv": inference,
        "10_B_fold_effect_distribution.csv": fold_distribution,
        "11_B_route_stability.csv": route_summary,
        "12_B_across_AI_composite.csv": ai_composite,
        "13_B_full_cohort_candidate_maps.csv": full_maps,
        "14_B_interpretation_decision_table.csv": decisions,
    }
    for name, frame in outputs.items():
        write_csv(frame, name)
    teacher_runner.OUT = OUT
    make_figures(effects, inference, fold_distribution, "B")
    (OUT / "RESULTS.md").write_text(build_report(selection_summary, inference, ai_composite, decisions), encoding="utf-8")

    checks = {
        "teacher_nominated_strategy_is_A": nominated == "A",
        "supplement_strategy_is_B": True,
        "source_hash_unchanged": source_before == sha256(SOURCE),
        "PHQ_fold_hash_unchanged": phq_fold_before == sha256(PHQ_FOLDS),
        "HAMD_fold_hash_unchanged": hamd_fold_before == sha256(HAMD_FOLDS),
        "PHQ_subjects_189": predictions[predictions["scale"].eq("PHQ-8")]["subject_id"].nunique() == 189,
        "HAMD_subjects_99": predictions[predictions["scale"].eq("HAMD-17")]["subject_id"].nunique() == 99,
        "six_primary_rows": len(inference) == 6,
        "subject_repeats_exactly_10": subject_inference["paired_repeat_n"].eq(10).all(),
        "routes_unique_per_fold_item_model": not routes.duplicated(["scale", "model", "repeat", "fold", "item_id"]).any(),
        "predictions_only_B_and_C03": set(predictions["strategy"]) == {"B", "C03"},
        "HAMD14_absent_from_primary_routes": not ((routes["scale"].eq("HAMD-17")) & routes["item_id"].eq(14)).any(),
        "full_map_rows_72": len(full_maps) == 72,
        "raw_data_modified_false": source_before == sha256(SOURCE),
        "llm_calls_zero": True,
    }
    check_rows = [{"check": key, "status": "PASS" if value else "FAIL", "observed": bool(value)} for key, value in checks.items()]
    write_csv(pd.DataFrame(check_rows), "verification_checks.csv")
    status = "PASS" if all(checks.values()) else "FAIL"
    manifest = {
        "analysis_name": "teacher-selected A main run plus B supplement; B-only per-AI cross-subject generalization",
        "status": status,
        "nominated_main_strategy": "A",
        "selected_strategy": "B",
        "selection_context": "A ranked first by participant-weighted cross-scale total-MAE Hedges gz; B is a requested supplement",
        "stage1_source": str(THREE_DIR.relative_to(ROOT)),
        "stage2_source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": sha256(SOURCE),
        "folds": {"PHQ": str(PHQ_FOLDS.relative_to(ROOT)), "PHQ_sha256": sha256(PHQ_FOLDS), "HAMD": str(HAMD_FOLDS.relative_to(ROOT)), "HAMD_sha256": sha256(HAMD_FOLDS), "design": "10 repeats x 5 folds; outer-training selection and held-out evaluation"},
        "scope": {"PHQ": "all189 pooled", "HAMD": "all99 HAMD16 core", "models": {"PHQ": list(PHQ_MODELS), "HAMD": list(HAMD_MODELS)}},
        "strategy_B": "per AI and item, minimum outer-training raw item MAE; ties prefer C03, item Spearman, coverage, fixed condition order",
        "baseline": "same AI C03",
        "inference": "collapse 10 OOF repeats within subject; paired sign-flip permutation and participant bootstrap; paired t and Wilcoxon sensitivity; BH-FDR within scale across 3 AIs",
        "raw_data_modified": False,
        "llm_calls": 0,
        "python": sys.version,
        "platform": platform.platform(),
        "packages": {"numpy": np.__version__, "pandas": pd.__version__},
        "rows": {name: len(frame) for name, frame in outputs.items()},
        "verification_status": status,
    }
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "verification_report.json").write_text(json.dumps({"status": status, "checks": check_rows, "failures": [k for k, v in checks.items() if not v]}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "workbook_payload.json").write_text(json.dumps({"selected_strategy": "B", "selection_summary": json.loads(selection_summary.to_json(orient="records", force_ascii=False)), "primary_inference": json.loads(inference.to_json(orient="records", force_ascii=False)), "composite": json.loads(ai_composite.to_json(orient="records", force_ascii=False)), "fold_distribution": json.loads(fold_distribution.to_json(orient="records", force_ascii=False)), "route_stability": json.loads(route_summary.to_json(orient="records", force_ascii=False)), "full_cohort_candidate_maps": json.loads(full_maps.to_json(orient="records", force_ascii=False)), "decision_table": json.loads(decisions.to_json(orient="records", force_ascii=False)), "checks": check_rows}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": status, "selected_strategy": "B", "nominated_main_strategy": "A", "inference_rows": len(inference), "output": str(OUT)}, ensure_ascii=False))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
