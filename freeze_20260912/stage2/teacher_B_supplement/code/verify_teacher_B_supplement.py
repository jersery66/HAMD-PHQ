"""Independent verification for the Strategy B supplement."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, ttest_rel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis" / "item_total_correlation"))
from all_item_valid_core import HAMD_MAX, PHQ_MAX  # noqa: E402
from run_item_total_all_valid import load_item_data  # noqa: E402
from run_teacher_focused_generalization import sha256  # noqa: E402

OUT = ROOT / "outputs" / "pdch_teacher_B_supplement_generalization_20260915"
SOURCE = ROOT / "outputs" / "pdch_all_prompt_fields_corrected_20260807" / "04_评分维度明细.csv"
PHQ_FOLDS = ROOT / "outputs" / "pdch_phq189_cross_ai_heterogeneity_20260909" / "PHQ_189_outer_folds.csv"
HAMD_FOLDS = ROOT / "outputs" / "pdch_hamd99_cross_ai_heterogeneity_20260909" / "HAMD_99_outer_folds.csv"
CONDITIONS = (3, 4, 7, 8, 11, 12, 15, 16)
EXPECTED = {
    SOURCE: "34ec669d677860b2b671d01f3f3d77a66d669ec693cd64cf42347eb1bdc2fa4d",
    PHQ_FOLDS: "12c219dfe3b6d31983f4f0acf5304ed2dee788aa9ee29fea48dd0a1edc5354d4",
    HAMD_FOLDS: "ca2feabcf6f175b8092596427f3645b2f95525ae3b6c29535e05266130bbeddf",
}


def cap(scale: str, item: int) -> int:
    return int((PHQ_MAX if scale == "PHQ-8" else HAMD_MAX)[int(item)])


def valid(frame: pd.DataFrame, scale: str, item: int) -> pd.DataFrame:
    maximum = cap(scale, item)
    mask = (
        np.isfinite(frame["predicted"])
        & np.isfinite(frame["gold_item"])
        & np.isfinite(frame["gold_total"])
        & frame["predicted"].between(0, maximum)
        & frame["predicted"].ne(9)
        & frame["gold_item"].between(0, maximum)
        & frame["gold_item"].ne(9)
    )
    return frame.loc[mask].copy()


def load_cube() -> pd.DataFrame:
    frame, _ = load_item_data(SOURCE)
    frame = frame[
        frame["thinking_mode"].astype(str).eq("思考")
        & pd.to_numeric(frame["condition_id"], errors="coerce").isin(CONDITIONS)
        & (
            (frame["scale"].eq("PHQ-8") & frame["cohort"].eq("DAIC-WOZ全量189人"))
            | (frame["scale"].eq("HAMD-17") & frame["cohort"].eq("PDCH标签99人"))
        )
    ].copy()
    frame["condition_id"] = pd.to_numeric(frame["condition_id"], errors="raise").astype(int)
    frame["item_id"] = pd.to_numeric(frame["item_id"], errors="raise").astype(int)
    frame["subject_id"] = frame["subject_id"].astype(str)
    frame["predicted"] = pd.to_numeric(frame["AI本题预测分数"], errors="coerce")
    frame["gold_item"] = pd.to_numeric(frame["金标准分数_gold_score"], errors="coerce")
    frame["gold_total"] = pd.to_numeric(frame["真实量表总分"], errors="coerce")
    return frame


def b_winner(frame: pd.DataFrame, scale: str, item: int) -> int:
    rows = []
    maximum = cap(scale, item)
    for condition in CONDITIONS:
        condition_frame = frame[frame["condition_id"].eq(condition)].copy()
        gold_valid = np.isfinite(condition_frame["gold_item"]) & condition_frame["gold_item"].between(0, maximum) & condition_frame["gold_item"].ne(9)
        usable = valid(condition_frame, scale, item)
        if len(usable):
            errors = usable["predicted"].to_numpy(float) - usable["gold_item"].to_numpy(float)
            item_mae = float(np.abs(errors).mean())
            rho = float(spearmanr(usable["predicted"], usable["gold_item"]).statistic) if usable["predicted"].nunique() > 1 and usable["gold_item"].nunique() > 1 else math.nan
        else:
            item_mae = math.nan
            rho = math.nan
        rows.append({"condition": condition, "item_mae": item_mae, "rho": rho, "coverage": float(len(usable) / gold_valid.sum()) if int(gold_valid.sum()) else math.nan})
    metrics = pd.DataFrame(rows)
    finite = metrics[np.isfinite(metrics["item_mae"])].copy()
    if finite.empty:
        return 3
    best = float(finite["item_mae"].min())
    tied = finite[np.isclose(finite["item_mae"], best, atol=1e-12, rtol=0)]
    if 3 in set(tied["condition"]):
        return 3
    tied = tied.assign(
        rho=tied["rho"].fillna(-math.inf),
        coverage=tied["coverage"].fillna(-math.inf),
        order=tied["condition"].map({condition: index for index, condition in enumerate(CONDITIONS)}),
    )
    return int(tied.sort_values(["rho", "coverage", "order"], ascending=[False, False, True]).iloc[0]["condition"])


def main() -> None:
    inference = pd.read_csv(OUT / "09_B_primary_inference.csv")
    routes = pd.read_csv(OUT / "04_B_outer_routes.csv")
    candidates = pd.read_csv(OUT / "05_B_training_candidate_metrics.csv", low_memory=False)
    predictions = pd.read_csv(OUT / "06_B_outer_oof_item_predictions.csv", dtype={"subject_id": str})
    subject_repeat = pd.read_csv(OUT / "07_B_subject_repeat_metrics.csv", dtype={"subject_id": str})
    subject = pd.read_csv(OUT / "08_B_subject_level_inference_data.csv", dtype={"subject_id": str})
    fold = pd.concat(
        [
            pd.read_csv(PHQ_FOLDS, dtype={"subject_id": str}).assign(scale="PHQ-8"),
            pd.read_csv(HAMD_FOLDS, dtype={"subject_id": str}).assign(scale="HAMD-17"),
        ],
        ignore_index=True,
    )
    pred_fold = predictions.merge(fold.rename(columns={"fold": "expected_fold"}), on=["scale", "repeat", "subject_id"], how="left", validate="many_to_one")
    pred_b = predictions[predictions["strategy"].eq("B")].merge(routes[["scale", "model", "repeat", "fold", "item_id", "selected_condition_id"]], on=["scale", "model", "repeat", "fold", "item_id"], how="left", suffixes=("_pred", "_route"), validate="many_to_one")
    candidate_selected = candidates[candidates["selected"].astype(str).str.lower().eq("true")]
    candidate_groups = candidates.groupby(["scale", "model", "repeat", "fold", "item_id"], sort=False).size()
    cube = load_cube()
    route_mismatches = 0
    for keys, group in routes.groupby(["scale", "model", "repeat", "fold", "item_id"], sort=True):
        scale, model, repeat, fold_id, item = keys
        frame = cube[cube["scale"].eq(scale) & cube["model"].eq(model) & cube["item_id"].eq(item)]
        test_ids = set(fold.loc[fold["scale"].eq(scale) & fold["repeat"].eq(repeat) & fold["fold"].eq(fold_id), "subject_id"].astype(str))
        frame = frame[~frame["subject_id"].isin(test_ids)]
        expected = b_winner(frame, scale, int(item))
        if expected != int(group.iloc[0]["selected_condition_id"]):
            route_mismatches += 1

    calc = predictions.copy()
    calc["error"] = calc["predicted_item"] - calc["gold_item"]
    calc["abs_error"] = calc["error"].abs()
    calc["item_nae_component"] = [abs(e) / cap(s, int(i)) for e, s, i in zip(calc["error"], calc["scale"], calc["item_id"])]
    group_key = ["scale", "model", "strategy", "repeat", "fold", "subject_id"]
    rebuilt = calc.groupby(group_key, as_index=False).agg(signed_sum=("error", "sum"), sum_item_AE=("abs_error", "sum"), item_NAE=("item_nae_component", "mean"))
    rebuilt["total_abs_error"] = rebuilt["signed_sum"].abs()
    compare = rebuilt.merge(subject_repeat[group_key + ["total_abs_error", "sum_item_AE", "item_NAE"]], on=group_key, how="outer", suffixes=("_recomputed", "_reported"), validate="one_to_one")
    metric_error = max(float(np.nanmax(np.abs(compare[f"{name}_recomputed"] - compare[f"{name}_reported"]))) for name in ("total_abs_error", "sum_item_AE", "item_NAE"))

    headline_error = 0.0
    t_error = 0.0
    for (scale, model), row_group in inference.groupby(["scale", "model"]):
        row = row_group.iloc[0]
        group = subject[subject["scale"].eq(scale) & subject["model"].eq(model)]
        headline_error = max(headline_error, abs(group["selected_total_MAE"].mean() - float(row["selected_total_MAE"])), abs(group["delta_total_MAE"].mean() - float(row["delta_total_MAE"])))
        t_error = max(t_error, abs(float(ttest_rel(group["selected_total_MAE"], group["C03_total_MAE"]).pvalue) - float(row["paired_t_p"])))

    checks = [
        ("source_and_fold_hashes_match", all(sha256(path) == expected for path, expected in EXPECTED.items()), {str(path): sha256(path) for path in EXPECTED}),
        ("nominated_main_strategy_A", json.loads((OUT / "run_manifest.json").read_text(encoding="utf-8"))["nominated_main_strategy"] == "A", "A"),
        ("supplement_strategy_B", json.loads((OUT / "run_manifest.json").read_text(encoding="utf-8"))["selected_strategy"] == "B", "B"),
        ("six_inference_rows", len(inference) == 6, len(inference)),
        ("candidate_groups_have_eight_conditions", candidate_groups.eq(8).all(), candidate_groups.value_counts().to_dict()),
        ("candidate_selection_matches_routes", (candidate_selected[["scale", "model", "repeat", "fold", "item_id", "condition_id"]].merge(routes[["scale", "model", "repeat", "fold", "item_id", "selected_condition_id"]], on=["scale", "model", "repeat", "fold", "item_id"], validate="one_to_one")["condition_id"] == candidate_selected[["scale", "model", "repeat", "fold", "item_id", "condition_id"]].merge(routes[["scale", "model", "repeat", "fold", "item_id", "selected_condition_id"]], on=["scale", "model", "repeat", "fold", "item_id"], validate="one_to_one")["selected_condition_id"]).all(), "candidate selected vs route"),
        ("all_routes_recomputed_as_B_training_only", route_mismatches == 0, route_mismatches),
        ("prediction_fold_membership_matches", (pred_fold["fold"] == pred_fold["expected_fold"]).all(), int((pred_fold["fold"] != pred_fold["expected_fold"]).sum())),
        ("B_prediction_conditions_match_routes", (pred_b["selected_condition_id_pred"] == pred_b["selected_condition_id_route"]).all(), int((pred_b["selected_condition_id_pred"] != pred_b["selected_condition_id_route"]).sum())),
        ("prediction_keys_unique", not predictions.duplicated(["scale", "model", "strategy", "repeat", "subject_id", "item_id"]).any(), int(predictions.duplicated(["scale", "model", "strategy", "repeat", "subject_id", "item_id"]).sum())),
        ("HAMD14_absent", not ((predictions["scale"] == "HAMD-17") & (predictions["item_id"] == 14)).any(), True),
        ("recomputed_subject_repeat_metrics", metric_error < 1e-12, metric_error),
        ("headline_means_recomputed", headline_error < 1e-12, headline_error),
        ("paired_t_recomputed", t_error < 1e-12, t_error),
        ("subjects_have_ten_repeats", subject["paired_repeat_n"].eq(10).all(), subject["paired_repeat_n"].value_counts().to_dict()),
        ("supported_cells_are_PHQ_DeepSeek_and_Qwen", set(map(tuple, inference.loc[inference["generalization_supported"].astype(str).str.lower().eq("true"), ["scale", "model"]].to_numpy())) == {("PHQ-8", "DeepSeek-V4-Pro"), ("PHQ-8", "Qwen3.7-Max")}, inference.loc[inference["generalization_supported"].astype(str).str.lower().eq("true"), ["scale", "model"]].to_dict("records")),
        ("full_maps_have_72_rows", len(pd.read_csv(OUT / "13_B_full_cohort_candidate_maps.csv")) == 72, len(pd.read_csv(OUT / "13_B_full_cohort_candidate_maps.csv"))),
    ]
    records = [{"check": name, "status": "PASS" if passed else "FAIL", "observed": observed} for name, passed, observed in checks]
    report = {"status": "PASS" if all(passed for _, passed, _ in checks) else "FAIL", "independent_recomputation": True, "checks": records, "failures": [name for name, passed, _ in checks if not passed]}
    (OUT / "independent_verification_checks.csv").write_text(pd.DataFrame(records).to_csv(index=False), encoding="utf-8-sig")
    (OUT / "independent_verification_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": len(checks), "failures": report["failures"]}, ensure_ascii=False))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
