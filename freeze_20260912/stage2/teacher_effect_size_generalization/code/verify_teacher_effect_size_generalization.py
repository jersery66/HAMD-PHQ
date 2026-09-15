"""Independent audit for the 2026-09-15 teacher-focused analysis.

The verifier does not import the analysis runner's selection functions. It
recomputes every outer-fold Strategy A route from the canonical item table,
checks OOF fold membership, rebuilds core error aggregates, and verifies the
headline inference table. It writes only audit artifacts into the derived
output directory.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, ttest_rel


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / "analysis" / "item_total_correlation"
sys.path.insert(0, str(ANALYSIS_DIR))

from all_item_valid_core import HAMD_MAX, PHQ_MAX  # noqa: E402
from run_item_total_all_valid import load_item_data  # noqa: E402


OUT = ROOT / "outputs" / "pdch_teacher_effect_size_selection_generalization_20260915"
SOURCE = ROOT / "outputs" / "pdch_all_prompt_fields_corrected_20260807" / "04_评分维度明细.csv"
PHQ_FOLDS = ROOT / "outputs" / "pdch_phq189_cross_ai_heterogeneity_20260909" / "PHQ_189_outer_folds.csv"
HAMD_FOLDS = ROOT / "outputs" / "pdch_hamd99_cross_ai_heterogeneity_20260909" / "HAMD_99_outer_folds.csv"
CONDITIONS = (3, 4, 7, 8, 11, 12, 15, 16)
EXPECTED_HASHES = {
    SOURCE: "34ec669d677860b2b671d01f3f3d77a66d669ec693cd64cf42347eb1bdc2fa4d",
    PHQ_FOLDS: "12c219dfe3b6d31983f4f0acf5304ed2dee788aa9ee29fea48dd0a1edc5354d4",
    HAMD_FOLDS: "ca2feabcf6f175b8092596427f3645b2f95525ae3b6c29535e05266130bbeddf",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def close(left: object, right: object, atol: float = 1e-10) -> bool:
    a = float(left)
    b = float(right)
    return (math.isnan(a) and math.isnan(b)) or math.isclose(a, b, abs_tol=atol, rel_tol=1e-10)


def maximum(scale: str, item_id: int) -> int:
    return int((PHQ_MAX if scale == "PHQ-8" else HAMD_MAX)[int(item_id)])


def bh(values: pd.Series) -> np.ndarray:
    p = values.to_numpy(float)
    order = np.argsort(p)
    ranked = p[order]
    adjusted = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    out = np.empty(len(p), dtype=float)
    out[order] = np.minimum(adjusted, 1.0)
    return out


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


def valid_condition_rows(frame: pd.DataFrame, scale: str, item_id: int) -> pd.DataFrame:
    cap = maximum(scale, item_id)
    valid = (
        np.isfinite(frame["predicted"])
        & np.isfinite(frame["gold_item"])
        & np.isfinite(frame["gold_total"])
        & frame["predicted"].between(0, cap)
        & frame["predicted"].ne(9)
        & frame["gold_item"].between(0, cap)
        & frame["gold_item"].ne(9)
    )
    return frame.loc[valid].copy()


def recompute_route_rows(cube: pd.DataFrame, routes: pd.DataFrame) -> tuple[int, float]:
    mismatch_count = 0
    max_rho_error = 0.0
    fold_paths = {"PHQ-8": PHQ_FOLDS, "HAMD-17": HAMD_FOLDS}
    for (scale, model, item_id), route_group in routes.groupby(["scale", "model", "item_id"], sort=True):
        base = cube[cube["scale"].eq(scale) & cube["model"].eq(model) & cube["item_id"].eq(item_id)].copy()
        valid_by_condition = {
            condition: valid_condition_rows(base[base["condition_id"].eq(condition)], scale, int(item_id)).set_index("subject_id")
            for condition in CONDITIONS
        }
        folds = pd.read_csv(fold_paths[scale], dtype={"subject_id": str})
        all_subjects = set(base["subject_id"].astype(str).unique())
        for route in route_group.itertuples(index=False):
            test_ids = set(
                folds.loc[(folds["repeat"] == route.repeat) & (folds["fold"] == route.fold), "subject_id"].astype(str)
            )
            train_ids = all_subjects - test_ids
            subject_sets = [set(frame.index).intersection(train_ids) for frame in valid_by_condition.values()]
            common = sorted(set.intersection(*subject_sets))
            scores: dict[int, float] = {}
            for condition, frame in valid_by_condition.items():
                group = frame.loc[common]
                pred = group["predicted"].to_numpy(float)
                corrected = group["gold_total"].to_numpy(float) - group["gold_item"].to_numpy(float)
                if len(common) >= 30 and len(np.unique(pred)) >= 2 and len(np.unique(corrected)) >= 2:
                    scores[condition] = float(spearmanr(pred, corrected).statistic)
                else:
                    scores[condition] = math.nan
            finite = {condition: value for condition, value in scores.items() if np.isfinite(value)}
            if not finite:
                expected = 3
                expected_rho = math.nan
            else:
                expected_rho = max(finite.values())
                tied = [condition for condition, value in finite.items() if np.isclose(value, expected_rho, atol=1e-12, rtol=0)]
                expected = 3 if 3 in tied else min(tied)
            if expected != int(route.selected_condition_id):
                mismatch_count += 1
            if np.isfinite(expected_rho) and np.isfinite(float(route.selected_training_corrected_rho)):
                max_rho_error = max(max_rho_error, abs(expected_rho - float(route.selected_training_corrected_rho)))
            elif not (math.isnan(expected_rho) and pd.isna(route.selected_training_corrected_rho)):
                mismatch_count += 1
    return mismatch_count, max_rho_error


def main() -> None:
    selection_composite = pd.read_csv(OUT / "02_strategy_selection_composite.csv")
    selection = pd.read_csv(OUT / "03_strategy_selection_summary.csv")
    routes = pd.read_csv(OUT / "04_A_outer_routes.csv")
    candidates = pd.read_csv(OUT / "05_A_training_candidate_metrics.csv", low_memory=False)
    predictions = pd.read_csv(OUT / "06_A_outer_oof_item_predictions.csv", dtype={"subject_id": str})
    subject_repeat = pd.read_csv(OUT / "07_A_subject_repeat_metrics.csv", dtype={"subject_id": str})
    subject = pd.read_csv(OUT / "08_A_subject_level_inference_data.csv", dtype={"subject_id": str})
    inference = pd.read_csv(OUT / "09_A_primary_inference.csv")
    folds_out = pd.read_csv(OUT / "10_A_fold_effect_distribution.csv")
    full_maps = pd.read_csv(OUT / "13_A_full_cohort_candidate_maps.csv")
    decisions = pd.read_csv(OUT / "14_interpretation_decision_table.csv")

    selected = selection.loc[selection["selected"].astype(str).str.lower().eq("true")]
    selection_error = 0.0
    for row in selection.itertuples(index=False):
        for scale, prefix in (("PHQ-8", "PHQ"), ("HAMD-17", "HAMD")):
            observed = selection_composite.loc[
                selection_composite["scale"].eq(scale) & selection_composite["strategy"].eq(row.strategy), "hedges_gz"
            ].iloc[0]
            selection_error = max(selection_error, abs(float(row._asdict()[f"{prefix}_effect_gz"]) - float(observed)))

    candidate_selected = candidates[candidates["selected"].astype(str).str.lower().eq("true")]
    candidate_key = ["scale", "model", "repeat", "fold", "item_id"]
    candidate_routes = candidate_selected[candidate_key + ["condition_id"]].merge(
        routes[candidate_key + ["selected_condition_id"]], on=candidate_key, how="outer", validate="one_to_one"
    )

    fold_tables = []
    for scale, path in (("PHQ-8", PHQ_FOLDS), ("HAMD-17", HAMD_FOLDS)):
        fold = pd.read_csv(path, dtype={"subject_id": str})[["repeat", "fold", "subject_id"]]
        fold["scale"] = scale
        fold_tables.append(fold)
    fold_lookup = pd.concat(fold_tables, ignore_index=True)
    pred_fold = predictions.merge(
        fold_lookup.rename(columns={"fold": "expected_fold"}),
        on=["scale", "repeat", "subject_id"],
        how="left",
        validate="many_to_one",
    )
    target_pred = predictions[predictions["strategy"].eq("A")].merge(
        routes[candidate_key + ["selected_condition_id"]], on=candidate_key, how="left", validate="many_to_one"
    )

    calc = predictions.copy()
    calc["error"] = calc["predicted_item"] - calc["gold_item"]
    calc["abs_error"] = calc["error"].abs()
    calc["item_nae_component"] = [
        abs(error) / maximum(scale, int(item_id))
        for error, scale, item_id in zip(calc["error"], calc["scale"], calc["item_id"])
    ]
    group_key = ["scale", "model", "strategy", "repeat", "fold", "subject_id"]
    rebuilt = calc.groupby(group_key, as_index=False).agg(
        item_count=("item_id", "nunique"),
        signed_sum=("error", "sum"),
        sum_item_AE=("abs_error", "sum"),
        item_NAE=("item_nae_component", "mean"),
    )
    rebuilt["total_abs_error"] = rebuilt["signed_sum"].abs()
    metric_compare = rebuilt.merge(
        subject_repeat[group_key + ["total_abs_error", "sum_item_AE", "item_NAE"]],
        on=group_key,
        suffixes=("_recomputed", "_reported"),
        how="outer",
        validate="one_to_one",
    )
    metric_error = max(
        np.nanmax(np.abs(metric_compare[f"{metric}_recomputed"] - metric_compare[f"{metric}_reported"]))
        for metric in ("total_abs_error", "sum_item_AE", "item_NAE")
    )

    headline_error = 0.0
    t_error = 0.0
    q_error = 0.0
    for (scale, model), row_group in inference.groupby(["scale", "model"]):
        row = row_group.iloc[0]
        group = subject[subject["scale"].eq(scale) & subject["model"].eq(model)]
        headline_error = max(
            headline_error,
            abs(group["selected_total_MAE"].mean() - float(row["selected_total_MAE"])),
            abs(group["C03_total_MAE"].mean() - float(row["C03_total_MAE"])),
            abs(group["delta_total_MAE"].mean() - float(row["delta_total_MAE"])),
        )
        t_p = float(ttest_rel(group["selected_total_MAE"], group["C03_total_MAE"]).pvalue)
        t_error = max(t_error, abs(t_p - float(row["paired_t_p"])))
    for _, indices in inference.groupby("scale").groups.items():
        recomputed_q = bh(inference.loc[indices, "sign_flip_p"])
        q_error = max(q_error, float(np.max(np.abs(recomputed_q - inference.loc[indices, "sign_flip_q"].to_numpy(float)))))

    fold_rebuilt = subject_repeat[subject_repeat["complete"].astype(str).str.lower().eq("true")].pivot(
        index=["scale", "model", "repeat", "fold", "subject_id"], columns="strategy", values="total_abs_error"
    ).reset_index()
    fold_rebuilt["delta_MAE"] = fold_rebuilt["A"] - fold_rebuilt["C03"]
    fold_rebuilt = fold_rebuilt.groupby(["scale", "model", "repeat", "fold"], as_index=False)["delta_MAE"].mean()
    fold_compare = fold_rebuilt.merge(
        folds_out[["scale", "model", "repeat", "fold", "delta_MAE"]],
        on=["scale", "model", "repeat", "fold"],
        suffixes=("_recomputed", "_reported"),
        how="outer",
        validate="one_to_one",
    )
    fold_error = float(np.max(np.abs(fold_compare["delta_MAE_recomputed"] - fold_compare["delta_MAE_reported"])))

    cube = load_cube()
    route_mismatches, max_rho_error = recompute_route_rows(cube, routes)

    checks: list[tuple[str, bool, object]] = [
        ("canonical_and_fold_hashes_match", all(sha256(path) == expected for path, expected in EXPECTED_HASHES.items()), {str(p): sha256(p) for p in EXPECTED_HASHES}),
        ("unique_selected_strategy_A", len(selected) == 1 and selected.iloc[0]["strategy"] == "A", selected["strategy"].tolist()),
        ("A_has_best_PHQ_and_HAMD_total_MAE_effect", all(selection.sort_values("PHQ_mean_delta_MAE").iloc[0]["strategy"] == "A" for _ in [0]) and selection.sort_values("HAMD_mean_delta_MAE").iloc[0]["strategy"] == "A", selection[["strategy", "PHQ_mean_delta_MAE", "HAMD_mean_delta_MAE", "PHQ_effect_rank", "HAMD_effect_rank"]].to_dict("records")),
        ("scale_specific_effect_recomputed", selection_error < 1e-12, selection_error),
        ("candidate_groups_have_eight_conditions", candidates.groupby(candidate_key).size().eq(8).all(), candidates.groupby(candidate_key).size().value_counts().to_dict()),
        ("candidate_selected_matches_route", (candidate_routes["condition_id"] == candidate_routes["selected_condition_id"]).all(), int((candidate_routes["condition_id"] != candidate_routes["selected_condition_id"]).sum())),
        ("all_outer_routes_recomputed_from_training_only", route_mismatches == 0 and max_rho_error < 1e-10, {"mismatches": route_mismatches, "max_rho_error": max_rho_error}),
        ("prediction_fold_membership_matches_frozen_folds", (pred_fold["fold"] == pred_fold["expected_fold"]).all(), int((pred_fold["fold"] != pred_fold["expected_fold"]).sum())),
        ("A_prediction_conditions_match_routes", (target_pred["selected_condition_id_x"] == target_pred["selected_condition_id_y"]).all(), int((target_pred["selected_condition_id_x"] != target_pred["selected_condition_id_y"]).sum())),
        ("C03_predictions_are_condition_3", predictions.loc[predictions["strategy"].eq("C03"), "selected_condition_id"].eq(3).all(), True),
        ("prediction_keys_unique", not predictions.duplicated(["scale", "model", "strategy", "repeat", "subject_id", "item_id"]).any(), int(predictions.duplicated(["scale", "model", "strategy", "repeat", "subject_id", "item_id"]).sum())),
        ("HAMD14_absent", not ((predictions["scale"] == "HAMD-17") & (predictions["item_id"] == 14)).any(), True),
        ("PHQ_and_HAMD_item_counts_are_8_and_16", rebuilt.groupby("scale")["item_count"].apply(lambda s: set(s)).to_dict() == {"HAMD-17": {16}, "PHQ-8": {8}}, rebuilt.groupby("scale")["item_count"].apply(lambda s: sorted(set(s))).to_dict()),
        ("subject_repeat_metrics_recomputed", metric_error < 1e-12, metric_error),
        ("each_subject_has_ten_paired_repeats", subject["paired_repeat_n"].eq(10).all(), subject["paired_repeat_n"].value_counts().to_dict()),
        ("headline_means_recomputed", headline_error < 1e-12, headline_error),
        ("paired_t_tests_recomputed", t_error < 1e-12, t_error),
        ("BH_FDR_recomputed_within_scale", q_error < 1e-12, q_error),
        ("fold_effects_recomputed", fold_error < 1e-12, fold_error),
        ("six_model_scale_cells", len(inference) == 6, len(inference)),
        ("supported_cells_are_PHQ_DeepSeek_and_Qwen", set(map(tuple, inference.loc[inference["generalization_supported"].astype(str).str.lower().eq("true"), ["scale", "model"]].to_numpy())) == {("PHQ-8", "DeepSeek-V4-Pro"), ("PHQ-8", "Qwen3.7-Max")}, inference.loc[inference["generalization_supported"].astype(str).str.lower().eq("true"), ["scale", "model"]].to_dict("records")),
        ("full_cohort_map_has_72_core_rows", len(full_maps) == 72 and not ((full_maps["scale"] == "HAMD-17") & (full_maps["item_id"] == 14)).any(), len(full_maps)),
        ("decision_table_has_six_rows", len(decisions) == 6, len(decisions)),
    ]
    records = [{"check": name, "status": "PASS" if passed else "FAIL", "observed": observed} for name, passed, observed in checks]
    report = {
        "status": "PASS" if all(passed for _, passed, _ in checks) else "FAIL",
        "independent_recomputation": True,
        "checks": records,
        "failures": [name for name, passed, _ in checks if not passed],
    }
    pd.DataFrame(records).to_csv(OUT / "independent_verification_checks.csv", index=False, encoding="utf-8-sig")
    (OUT / "independent_verification_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": len(checks), "failures": report["failures"]}, ensure_ascii=False))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
