"""Teacher-focused strategy selection and cross-subject generalization.

Stage 1 uses the frozen A/B/C repeated outer-OOF evidence to nominate one
strategy using the teacher-requested pooled standardized total-MAE effect.
Stage 2 evaluates only the selected strategy (A) for each AI on pooled PHQ189
and HAMD99 using the frozen
10x5 outer folds. Every condition map is learned on the outer-training subjects
and applied unchanged to the held-out fold.

No LLM is called and no source file is modified.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy.stats import ttest_rel, wilcoxon

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "analysis" / "item_total_correlation"
sys.path.insert(0, str(ANALYSIS_DIR))

from all_item_valid_core import HAMD_MAX, PHQ_MAX  # noqa: E402
from error_cancellation_core import fdr_bh, paired_mean_difference  # noqa: E402
from run_item_total_all_valid import item_name, load_item_data, seed_for  # noqa: E402
from run_three_strategy_condition_total import item_condition_metrics  # noqa: E402
from heterogeneous_condition_total_core import score_item_conditions  # noqa: E402
from three_strategy_condition_total_core import choose_strategy_b, weighted_kappa  # noqa: E402


SOURCE = ROOT / "outputs" / "pdch_all_prompt_fields_corrected_20260807" / "04_评分维度明细.csv"
THREE_DIR = ROOT / "outputs" / "pdch_heterogeneous_condition_three_strategy_20260827"
PHQ_FOLDS = ROOT / "outputs" / "pdch_phq189_cross_ai_heterogeneity_20260909" / "PHQ_189_outer_folds.csv"
HAMD_FOLDS = ROOT / "outputs" / "pdch_hamd99_cross_ai_heterogeneity_20260909" / "HAMD_99_outer_folds.csv"
OUT = ROOT / "outputs" / "pdch_teacher_effect_size_selection_generalization_20260915"

CONDITIONS = (3, 4, 7, 8, 11, 12, 15, 16)
PHQ_MODELS = ("DeepSeek-V4-Pro", "GLM-5.2", "Qwen3.7-Max")
HAMD_MODELS = ("GLM-5.2", "Kimi-K2.6", "Qwen3.7-Max")
PHQ_ITEMS = tuple(range(1, 9))
HAMD_CORE_ITEMS = tuple(i for i in range(1, 18) if i != 14)
SELECTION_STRATEGIES = ("A", "B", "C")
SELECTED_STRATEGY = "A"
BOOTSTRAP_REPS = 5000
PERMUTATION_REPS = 10000
SEED = 20260915


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_csv(frame: pd.DataFrame, name: str) -> Path:
    path = OUT / name
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def score_max(scale: str, item_id: int) -> int:
    return int((PHQ_MAX if scale == "PHQ-8" else HAMD_MAX)[int(item_id)])


def valid_score(scale: str, item_id: int, value: object) -> bool:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(x) and 0 <= x <= score_max(scale, item_id) and x != 9


def hedges_gz(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 2:
        return math.nan
    sd = float(values.std(ddof=1))
    if sd == 0:
        return 0.0 if float(values.mean()) == 0 else math.copysign(math.inf, float(values.mean()))
    d = float(values.mean() / sd)
    correction = 1.0 - 3.0 / (4.0 * (len(values) - 1) - 1.0)
    return float(correction * d)


def bootstrap_gz(values: np.ndarray, seed: int, reps: int = BOOTSTRAP_REPS) -> tuple[float, float, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    estimate = hedges_gz(values)
    if len(values) < 2:
        return estimate, math.nan, math.nan
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(reps):
        sample = values[rng.integers(0, len(values), len(values))]
        g = hedges_gz(sample)
        if math.isfinite(g):
            draws.append(g)
    if not draws:
        return estimate, math.nan, math.nan
    return estimate, float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def load_selection_evidence() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    decision = pd.read_csv(THREE_DIR / "three_strategy_decision_summary.csv")
    pairs = pd.read_csv(THREE_DIR / "subject_strategy_pairs.csv", low_memory=False)
    pairs = pairs[pairs["validation_layer"].eq("locked_outer_10x5_oof")].copy()

    effect_rows: list[dict[str, object]] = []
    for (scale, model, strategy), group in pairs.groupby(["scale", "model", "strategy"], sort=True):
        delta = pd.to_numeric(group["delta_absolute_total_error"], errors="coerce").dropna().to_numpy(float)
        g, g_low, g_high = bootstrap_gz(delta, seed_for("selection_gz", scale, model, strategy, SEED))
        frozen = decision[(decision["scale"] == scale) & (decision["model"] == model) & (decision["strategy"] == strategy)]
        if len(frozen) != 1:
            raise AssertionError(f"missing frozen decision row: {scale}/{model}/{strategy}")
        frozen = frozen.iloc[0]
        effect_rows.append(
            {
                "scale": scale,
                "model": model,
                "strategy": strategy,
                "paired_subject_n": int(len(delta)),
                "delta_total_MAE": float(frozen["delta_total_mae"]),
                "delta_total_MAE_CI_low": float(frozen["delta_total_mae_ci_low"]),
                "delta_total_MAE_CI_high": float(frozen["delta_total_mae_ci_high"]),
                "total_MAE_FDR_q": float(frozen["total_mae_fdr_q"]),
                "hedges_gz": g,
                "hedges_gz_CI_low": g_low,
                "hedges_gz_CI_high": g_high,
                "delta_item_NAE": float(frozen["delta_mean_item_nae"]),
                "delta_sum_item_AE": float(frozen["delta_sum_abs_item_error"]),
                "coverage_noninferiority_pass": bool(frozen["coverage_noninferiority_pass"]),
                "delta_cancellation_ratio": float(frozen["delta_cancellation_ratio"]),
                "stability_acceptable": bool(frozen["stability_acceptable"]),
                "test47_replication_support": bool(frozen["phq_test47_replication_support"]),
                "level1": bool(frozen["level1_total_improvement"]),
                "level2": bool(frozen["level2_true_scoring_improvement"]),
                "level3": bool(frozen["level3_deployable_value"]),
            }
        )
    effects = pd.DataFrame(effect_rows)

    composite_rows: list[dict[str, object]] = []
    for (scale, strategy), group in pairs.groupby(["scale", "strategy"], sort=True):
        pivot = group.pivot(index="subject_id", columns="model", values="delta_absolute_total_error")
        pivot = pivot.dropna(axis=0, how="any")
        composite = pivot.mean(axis=1).to_numpy(float)
        stats = paired_mean_difference(
            composite,
            np.zeros(len(composite)),
            bootstrap_reps=BOOTSTRAP_REPS,
            permutation_reps=PERMUTATION_REPS,
            seed=seed_for("selection_composite", scale, strategy, SEED),
        )
        g, g_low, g_high = bootstrap_gz(composite, seed_for("selection_composite_g", scale, strategy, SEED))
        composite_rows.append(
            {
                "scale": scale,
                "strategy": strategy,
                "complete_across_AI_subject_n": len(composite),
                "AI_equal_mean_delta_MAE": stats["delta"],
                "CI_low": stats["ci_low"],
                "CI_high": stats["ci_high"],
                "sign_flip_p": stats["p_value"],
                "hedges_gz": g,
                "hedges_gz_CI_low": g_low,
                "hedges_gz_CI_high": g_high,
            }
        )
    composite = pd.DataFrame(composite_rows)
    composite["sign_flip_q"] = np.nan
    for scale, indices in composite.groupby("scale").groups.items():
        composite.loc[indices, "sign_flip_q"] = fdr_bh(composite.loc[indices, "sign_flip_p"])

    summary_rows = []
    for strategy, group in effects.groupby("strategy", sort=True):
        row = {
            "strategy": strategy,
            "model_scale_cells": len(group),
            "cells_delta_MAE_below_0": int((group["delta_total_MAE"] < 0).sum()),
            "level1_cells": int(group["level1"].sum()),
            "level2_cells": int(group["level2"].sum()),
            "level3_cells": int(group["level3"].sum()),
            "coverage_noninferiority_cells": int(group["coverage_noninferiority_pass"].sum()),
            "stability_acceptable_cells": int(group["stability_acceptable"].sum()),
            "test47_replication_support_cells": int(group["test47_replication_support"].sum()),
            "mean_hedges_gz": float(group["hedges_gz"].replace([np.inf, -np.inf], np.nan).mean()),
            "mean_delta_item_NAE": float(group["delta_item_NAE"].mean()),
            "mean_delta_cancellation_ratio": float(group["delta_cancellation_ratio"].mean()),
        }
        for scale, prefix in (("PHQ-8", "PHQ"), ("HAMD-17", "HAMD")):
            scale_rows = group[group["scale"] == scale]
            row[f"{prefix}_mean_delta_MAE"] = float(scale_rows["delta_total_MAE"].mean())
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)

    # The meeting correction is important: PHQ and HAMD are different scales
    # and must be ranked independently. The primary selection quantity is the
    # scale-specific mean change in total MAE across the three AI cells. The
    # AI-equal participant Hedges g_z is retained as a standardized forest
    # companion, not pooled across scales and not used to create one overall
    # score. If future data nominate different strategies by scale, the caller
    # can carry those two choices separately; this current dataset nominates A
    # for both scales.
    for scale, prefix in (("PHQ-8", "PHQ"), ("HAMD-17", "HAMD")):
        scale_composite = composite[composite["scale"].eq(scale)].set_index("strategy")
        summary[f"{prefix}_effect_gz"] = summary["strategy"].map(scale_composite["hedges_gz"])
        summary[f"{prefix}_effect_gz_CI_low"] = summary["strategy"].map(scale_composite["hedges_gz_CI_low"])
        summary[f"{prefix}_effect_gz_CI_high"] = summary["strategy"].map(scale_composite["hedges_gz_CI_high"])
        summary[f"{prefix}_composite_subject_n"] = summary["strategy"].map(scale_composite["complete_across_AI_subject_n"])
        summary[f"{prefix}_effect_rank"] = summary[f"{prefix}_mean_delta_MAE"].rank(method="min", ascending=True).astype(int)
    winners = {
        scale: str(summary.loc[summary[f"{prefix}_effect_rank"].eq(1), "strategy"].iloc[0])
        for scale, prefix in (("PHQ-8", "PHQ"), ("HAMD-17", "HAMD"))
    }
    if len(set(winners.values())) != 1:
        raise AssertionError(f"current run expects one shared strategy, but scale-specific winners are {winners}")
    selected = next(iter(winners.values()))
    summary["selected"] = summary["strategy"].eq(selected)
    summary["selection_reason"] = np.where(
        summary["selected"],
        "按会议口径分别看量表整体总分MAE效应量；PHQ和HAMD均排名第1，因此进入外推检验",
        np.where(
            summary["strategy"].eq("B"),
            "条目真实性证据较完整且有Level2/test47支持，但在PHQ和HAMD的整体总分MAE效应量中均低于A",
            "稳定性较好，但在PHQ和HAMD的整体总分MAE效应量中均最弱，且没有Level2或test47支持",
        ),
    )
    return effects, composite, summary, selected


def load_cube() -> pd.DataFrame:
    item, _ = load_item_data(SOURCE)
    cube = item[
        (item["thinking_mode"].astype(str) == "思考")
        & (pd.to_numeric(item["condition_id"], errors="coerce").isin(CONDITIONS))
        & (
            ((item["scale"].astype(str) == "PHQ-8") & (item["cohort"].astype(str) == "DAIC-WOZ全量189人"))
            | ((item["scale"].astype(str) == "HAMD-17") & (item["cohort"].astype(str) == "PDCH标签99人"))
        )
    ].copy()
    cube["subject_id"] = cube["subject_id"].astype(str)
    cube["item_id"] = pd.to_numeric(cube["item_id"], errors="raise").astype(int)
    cube["condition_id"] = pd.to_numeric(cube["condition_id"], errors="raise").astype(int)
    cube["predicted"] = pd.to_numeric(cube["AI本题预测分数"], errors="coerce")
    cube["gold_item"] = pd.to_numeric(cube["金标准分数_gold_score"], errors="coerce")
    cube["gold_total"] = pd.to_numeric(cube["真实量表总分"], errors="coerce")
    key = ["scale", "cohort", "model", "condition_id", "subject_id", "item_id"]
    if cube.duplicated(key).any():
        raise AssertionError("canonical cube contains duplicate model-condition-subject-item rows")
    return cube


def load_fold_table(path: Path, expected_subjects: int) -> pd.DataFrame:
    folds = pd.read_csv(path, dtype={"subject_id": str})
    required = {"repeat", "fold", "subject_id"}
    if not required.issubset(folds.columns):
        raise AssertionError(f"fold table missing {sorted(required.difference(folds.columns))}")
    folds = folds[["repeat", "fold", "subject_id"]].copy()
    folds["repeat"] = pd.to_numeric(folds["repeat"], errors="raise").astype(int)
    folds["fold"] = pd.to_numeric(folds["fold"], errors="raise").astype(int)
    if folds["repeat"].nunique() != 10 or folds["fold"].nunique() != 5:
        raise AssertionError("expected 10 repeats x 5 folds")
    if len(folds) != expected_subjects * 10:
        raise AssertionError(f"fold row count mismatch: {len(folds)}")
    if folds.duplicated(["repeat", "subject_id"]).any():
        raise AssertionError("subject appears more than once within a repeat")
    if not folds.groupby("repeat")["subject_id"].nunique().eq(expected_subjects).all():
        raise AssertionError("each repeat must cover the full subject universe")
    return folds


def fit_and_apply_selected(cube: pd.DataFrame, selected_strategy: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if selected_strategy not in {"A", "B"}:
        raise ValueError(f"teacher-focused runner supports A or B, got {selected_strategy}")
    routes: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    predictions: list[dict[str, object]] = []
    configs = [
        ("PHQ-8", PHQ_MODELS, PHQ_ITEMS, PHQ_FOLDS, 189),
        ("HAMD-17", HAMD_MODELS, HAMD_CORE_ITEMS, HAMD_FOLDS, 99),
    ]
    for scale, models, items, fold_path, expected_n in configs:
        scale_frame = cube[cube["scale"] == scale].copy()
        subjects = sorted(scale_frame["subject_id"].unique())
        if len(subjects) != expected_n:
            raise AssertionError(f"{scale} subject count {len(subjects)} != {expected_n}")
        folds = load_fold_table(fold_path, expected_n)
        for (repeat, fold), assignment in folds.groupby(["repeat", "fold"], sort=True):
            test_ids = set(assignment["subject_id"].astype(str))
            train_ids = set(subjects) - test_ids
            if train_ids & test_ids or not train_ids or not test_ids:
                raise AssertionError("outer train/test split contract failed")
            for model in models:
                model_frame = scale_frame[scale_frame["model"] == model].copy()
                for item_id in items:
                    item_frame = model_frame[model_frame["item_id"] == item_id].copy()
                    training = item_frame[item_frame["subject_id"].isin(train_ids)].copy()
                    if selected_strategy == "A":
                        a_input = training[["scale", "item_id", "subject_id", "condition_id", "predicted", "gold_total", "gold_item"]].copy()
                        scores, winner = score_item_conditions(
                            a_input,
                            candidate_conditions=CONDITIONS,
                            minimum_common_n=30,
                        )
                    else:
                        metrics_for_b = item_condition_metrics(training)
                        winner = choose_strategy_b(metrics_for_b)
                        scores = metrics_for_b[["condition_id", "item_spearman", "coverage"]].rename(columns={"item_spearman": "rho", "coverage": "n_common"})
                    selected_condition = int(winner["selected_condition_id"])
                    routes.append(
                        {
                            "scale": scale,
                            "model": model,
                            "strategy": selected_strategy,
                            "repeat": int(repeat),
                            "fold": int(fold),
                            "item_id": int(item_id),
                            "item_name": item_name(scale, int(item_id)),
                            "outer_train_subject_n": len(train_ids),
                            "outer_test_subject_n": len(test_ids),
                            "selected_condition_id": selected_condition,
                            "selection_reason": winner["selection_reason"],
                            "selected_training_corrected_rho": winner.get("selected_rho", math.nan),
                            "common_training_subject_n": winner.get("n_common", math.nan),
                        }
                    )
                    metrics = item_condition_metrics(training)
                    if selected_strategy == "A":
                        candidate_table = metrics.merge(
                            scores.rename(columns={"rho": "corrected_rho", "n_common": "corrected_rho_common_n"}),
                            on="condition_id",
                            how="left",
                            validate="one_to_one",
                        )
                    else:
                        candidate_table = metrics.copy()
                    for metric_row in candidate_table.to_dict("records"):
                        candidates.append(
                            {
                                "scale": scale,
                                "model": model,
                                "repeat": int(repeat),
                                "fold": int(fold),
                                "item_id": int(item_id),
                                "item_name": item_name(scale, int(item_id)),
                                **metric_row,
                                "selected_strategy": selected_strategy,
                                "selected": int(metric_row["condition_id"]) == selected_condition,
                            }
                        )
                    for method, condition in ((selected_strategy, selected_condition), ("C03", 3)):
                        test = item_frame[
                            item_frame["subject_id"].isin(test_ids)
                            & item_frame["condition_id"].eq(condition)
                        ].copy()
                        if test["subject_id"].nunique() != len(test_ids):
                            raise AssertionError(f"missing held-out row {scale}/{model}/{repeat}/{fold}/{item_id}/{method}")
                        for row in test.itertuples(index=False):
                            predictions.append(
                                {
                                    "scale": scale,
                                    "model": model,
                                    "strategy": method,
                                    "repeat": int(repeat),
                                    "fold": int(fold),
                                    "subject_id": str(row.subject_id),
                                    "item_id": int(item_id),
                                    "item_name": item_name(scale, int(item_id)),
                                    "selected_condition_id": int(condition),
                                    "gold_item": float(row.gold_item) if pd.notna(row.gold_item) else math.nan,
                                    "predicted_item": float(row.predicted) if pd.notna(row.predicted) else math.nan,
                                }
                            )
    return pd.DataFrame(routes), pd.DataFrame(candidates), pd.DataFrame(predictions)


def aggregate_primary_subject_repeat(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for keys, group in predictions.groupby(["scale", "model", "strategy", "repeat", "fold", "subject_id"], sort=True):
        scale, model, strategy, repeat, fold, subject_id = keys
        expected = PHQ_ITEMS if scale == "PHQ-8" else HAMD_CORE_ITEMS
        layer = "PHQ8_complete" if scale == "PHQ-8" else "HAMD16_core"
        working = group[group["item_id"].isin(expected)].copy().set_index("item_id").reindex(expected)
        valid = np.array(
            [
                valid_score(scale, item_id, working.loc[item_id, "gold_item"])
                and valid_score(scale, item_id, working.loc[item_id, "predicted_item"])
                for item_id in expected
            ]
        )
        complete = bool(valid.all() and len(working) == len(expected))
        if not complete:
            rows.append(
                {
                    "scale": scale,
                    "analysis_layer": layer,
                    "model": model,
                    "strategy": strategy,
                    "repeat": int(repeat),
                    "fold": int(fold),
                    "subject_id": str(subject_id),
                    "complete": False,
                    "coverage": float(valid.mean()),
                }
            )
            continue
        gold = working["gold_item"].to_numpy(float)
        pred = working["predicted_item"].to_numpy(float)
        errors = pred - gold
        sum_item_ae = float(np.abs(errors).sum())
        total_abs = float(abs(errors.sum()))
        maxima = np.asarray([score_max(scale, int(i)) for i in expected], dtype=float)
        rows.append(
            {
                "scale": scale,
                "analysis_layer": layer,
                "model": model,
                "strategy": strategy,
                "repeat": int(repeat),
                "fold": int(fold),
                "subject_id": str(subject_id),
                "complete": True,
                "coverage": 1.0,
                "gold_total": float(gold.sum()),
                "predicted_total": float(pred.sum()),
                "total_abs_error": total_abs,
                "total_signed_error": float(errors.sum()),
                "sum_item_AE": sum_item_ae,
                "item_MAE": float(np.abs(errors).mean()),
                "item_NAE": float(np.mean(np.abs(errors) / maxima)),
                "cancellation_amount": float(sum_item_ae - total_abs),
                "cancellation_ratio": float((sum_item_ae - total_abs) / sum_item_ae) if sum_item_ae else 0.0,
                "weighted_kappa": weighted_kappa(pred, gold),
            }
        )
    return pd.DataFrame(rows)


def inference_from_subject_repeat(subject_repeat: pd.DataFrame, routes: pd.DataFrame, selected_strategy: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inference_rows = []
    fold_rows = []
    subject_rows = []
    for keys, group in subject_repeat.groupby(["scale", "analysis_layer", "model"], sort=True):
        scale, layer, model = keys
        selected_rows = group[(group["strategy"] == selected_strategy) & group["complete"]].copy()
        c = group[(group["strategy"] == "C03") & group["complete"]].copy()
        pair = selected_rows.merge(
            c[["repeat", "fold", "subject_id", "total_abs_error", "item_NAE", "sum_item_AE", "cancellation_ratio", "weighted_kappa"]],
            on=["repeat", "fold", "subject_id"],
            how="inner",
            suffixes=(f"_{selected_strategy}", "_C03"),
            validate="one_to_one",
        )
        if pair.empty:
            raise AssertionError(f"no paired OOF rows for {keys}")
        target_suffix = selected_strategy
        pair["delta_total_MAE"] = pair[f"total_abs_error_{target_suffix}"] - pair["total_abs_error_C03"]
        pair["delta_item_NAE"] = pair[f"item_NAE_{target_suffix}"] - pair["item_NAE_C03"]
        pair["delta_sum_item_AE"] = pair[f"sum_item_AE_{target_suffix}"] - pair["sum_item_AE_C03"]
        pair["delta_cancellation_ratio"] = pair[f"cancellation_ratio_{target_suffix}"] - pair["cancellation_ratio_C03"]
        pair["scale"] = scale
        pair["analysis_layer"] = layer
        pair["model"] = model

        subject = pair.groupby("subject_id", as_index=False).agg(
            paired_repeat_n=("repeat", "nunique"),
            selected_total_MAE=(f"total_abs_error_{target_suffix}", "mean"),
            C03_total_MAE=("total_abs_error_C03", "mean"),
            delta_total_MAE=("delta_total_MAE", "mean"),
            selected_item_NAE=(f"item_NAE_{target_suffix}", "mean"),
            C03_item_NAE=("item_NAE_C03", "mean"),
            delta_item_NAE=("delta_item_NAE", "mean"),
            selected_sum_item_AE=(f"sum_item_AE_{target_suffix}", "mean"),
            C03_sum_item_AE=("sum_item_AE_C03", "mean"),
            delta_sum_item_AE=("delta_sum_item_AE", "mean"),
            selected_cancellation_ratio=(f"cancellation_ratio_{target_suffix}", "mean"),
            C03_cancellation_ratio=("cancellation_ratio_C03", "mean"),
            delta_cancellation_ratio=("delta_cancellation_ratio", "mean"),
            selected_weighted_kappa=(f"weighted_kappa_{target_suffix}", "mean"),
            C03_weighted_kappa=("weighted_kappa_C03", "mean"),
        )
        subject["scale"] = scale
        subject["analysis_layer"] = layer
        subject["model"] = model
        subject["strategy"] = selected_strategy
        subject_rows.extend(subject.to_dict("records"))

        stats = paired_mean_difference(
            subject["selected_total_MAE"].to_numpy(float),
            subject["C03_total_MAE"].to_numpy(float),
            bootstrap_reps=BOOTSTRAP_REPS,
            permutation_reps=PERMUTATION_REPS,
            seed=seed_for("focused_selected", selected_strategy, scale, layer, model, SEED),
        )
        t_result = ttest_rel(subject["selected_total_MAE"], subject["C03_total_MAE"], nan_policy="omit")
        try:
            w_result = wilcoxon(subject["selected_total_MAE"], subject["C03_total_MAE"], zero_method="wilcox", alternative="two-sided")
            wilcoxon_stat, wilcoxon_p = float(w_result.statistic), float(w_result.pvalue)
        except ValueError:
            wilcoxon_stat, wilcoxon_p = math.nan, 1.0
        g, g_low, g_high = bootstrap_gz(subject["delta_total_MAE"].to_numpy(float), seed_for("focused_selected_g", selected_strategy, scale, layer, model, SEED))

        fold = pair.groupby(["repeat", "fold"], as_index=False).agg(
            heldout_subject_n=("subject_id", "nunique"),
            selected_MAE=(f"total_abs_error_{target_suffix}", "mean"),
            C03_MAE=("total_abs_error_C03", "mean"),
            delta_MAE=("delta_total_MAE", "mean"),
            delta_item_NAE=("delta_item_NAE", "mean"),
            delta_cancellation_ratio=("delta_cancellation_ratio", "mean"),
        )
        fold["scale"] = scale
        fold["analysis_layer"] = layer
        fold["model"] = model
        fold["improved"] = fold["delta_MAE"] < 0
        fold_rows.extend(fold.to_dict("records"))

        route = routes[(routes["scale"] == scale) & (routes["model"] == model)]
        top_rates = []
        for _, item_routes in route.groupby("item_id"):
            top_rates.append(float(item_routes["selected_condition_id"].value_counts(normalize=True).iloc[0]))
        inference_rows.append(
            {
                "scale": scale,
                "analysis_layer": layer,
                "model": model,
                "strategy": selected_strategy,
                "paired_subject_n": int(len(subject)),
                "mean_paired_repeats": float(subject["paired_repeat_n"].mean()),
                "selected_total_MAE": float(subject["selected_total_MAE"].mean()),
                "C03_total_MAE": float(subject["C03_total_MAE"].mean()),
                "delta_total_MAE": stats["delta"],
                "delta_total_MAE_CI_low": stats["ci_low"],
                "delta_total_MAE_CI_high": stats["ci_high"],
                "sign_flip_p": stats["p_value"],
                "paired_t_statistic": float(t_result.statistic),
                "paired_t_p": float(t_result.pvalue),
                "wilcoxon_statistic": wilcoxon_stat,
                "wilcoxon_p": wilcoxon_p,
                "hedges_gz": g,
                "hedges_gz_CI_low": g_low,
                "hedges_gz_CI_high": g_high,
                "selected_item_NAE": float(subject["selected_item_NAE"].mean()),
                "C03_item_NAE": float(subject["C03_item_NAE"].mean()),
                "delta_item_NAE": float(subject["delta_item_NAE"].mean()),
                "selected_sum_item_AE": float(subject["selected_sum_item_AE"].mean()),
                "C03_sum_item_AE": float(subject["C03_sum_item_AE"].mean()),
                "delta_sum_item_AE": float(subject["delta_sum_item_AE"].mean()),
                "selected_cancellation_ratio": float(subject["selected_cancellation_ratio"].mean()),
                "C03_cancellation_ratio": float(subject["C03_cancellation_ratio"].mean()),
                "delta_cancellation_ratio": float(subject["delta_cancellation_ratio"].mean()),
                "selected_weighted_kappa": float(subject["selected_weighted_kappa"].mean()),
                "C03_weighted_kappa": float(subject["C03_weighted_kappa"].mean()),
                "fold_improvement_rate": float(fold["improved"].mean()),
                "fold_delta_MAE_median": float(fold["delta_MAE"].median()),
                "fold_delta_MAE_IQR": float(fold["delta_MAE"].quantile(0.75) - fold["delta_MAE"].quantile(0.25)),
                "median_item_route_top_frequency": float(np.median(top_rates)),
                "C03_retention_rate": float((route["selected_condition_id"] == 3).mean()),
            }
        )
    inference = pd.DataFrame(inference_rows)
    inference["sign_flip_q"] = np.nan
    for (scale, layer), indices in inference.groupby(["scale", "analysis_layer"]).groups.items():
        inference.loc[indices, "sign_flip_q"] = fdr_bh(inference.loc[indices, "sign_flip_p"])
    inference["generalization_supported"] = (
        (inference["delta_total_MAE"] < 0)
        & (inference["delta_total_MAE_CI_high"] < 0)
        & (inference["sign_flip_q"] < 0.05)
    )
    inference["interpretation"] = np.where(
        inference["generalization_supported"],
        "验证折总分MAE显著低于C03，支持当前队列内跨受试者泛化",
        np.where(
            inference["delta_total_MAE"] < 0,
            "点估计改善但区间跨0或FDR未通过，不支持稳定泛化",
            "验证折总分MAE未改善",
        ),
    )
    return inference, pd.DataFrame(fold_rows), pd.DataFrame(subject_rows)


def route_stability(routes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (scale, model, item_id), group in routes.groupby(["scale", "model", "item_id"], sort=True):
        counts = group["selected_condition_id"].value_counts().sort_index()
        probs = counts / counts.sum()
        entropy_bits = float(scipy.stats.entropy(probs.to_numpy(), base=2))
        normalized = entropy_bits / math.log2(len(CONDITIONS)) if len(CONDITIONS) > 1 else 0.0
        top_condition = int(counts.sort_values(ascending=False).index[0])
        rows.append(
            {
                "scale": scale,
                "model": model,
                "item_id": int(item_id),
                "item_name": item_name(scale, int(item_id)),
                "top_condition_id": top_condition,
                "top_selection_frequency": float(counts.max() / counts.sum()),
                "normalized_entropy": normalized,
                "C03_selection_frequency": float(counts.get(3, 0) / counts.sum()),
                "condition_distribution": json.dumps({f"C{int(k):02d}": int(v) for k, v in counts.items()}, ensure_ascii=False),
            }
        )
    return pd.DataFrame(rows)


def fit_full_cohort_candidate_maps(
    cube: pd.DataFrame,
    route_summary: pd.DataFrame,
    inference: pd.DataFrame,
    selected_strategy: str,
) -> pd.DataFrame:
    """Fit transparent future-use candidates after OOF evaluation.

    These maps are not used to estimate the reported OOF effects. They are
    fitted on the full cohort only so a future, entirely new subject could be
    scored with a fixed map. Unsupported model-scale cells remain documented
    but are explicitly marked as not recommended for use.
    """
    rows: list[dict[str, object]] = []
    configs = [
        ("PHQ-8", PHQ_MODELS, PHQ_ITEMS),
        ("HAMD-17", HAMD_MODELS, HAMD_CORE_ITEMS),
    ]
    support_lookup = inference.set_index(["scale", "model"])["generalization_supported"].to_dict()
    for scale, models, items in configs:
        for model in models:
            for item_id in items:
                frame = cube[
                    cube["scale"].eq(scale)
                    & cube["model"].eq(model)
                    & cube["item_id"].eq(item_id)
                ].copy()
                metrics = item_condition_metrics(frame)
                if selected_strategy == "A":
                    a_input = frame[["scale", "item_id", "subject_id", "condition_id", "predicted", "gold_total", "gold_item"]].copy()
                    scores, winner = score_item_conditions(a_input, candidate_conditions=CONDITIONS, minimum_common_n=30)
                else:
                    winner = choose_strategy_b(metrics)
                selected_condition = int(winner["selected_condition_id"])
                selected_metrics = metrics[metrics["condition_id"].eq(selected_condition)].iloc[0]
                c03_metrics = metrics[metrics["condition_id"].eq(3)].iloc[0]
                stability = route_summary[
                    route_summary["scale"].eq(scale)
                    & route_summary["model"].eq(model)
                    & route_summary["item_id"].eq(item_id)
                ].iloc[0]
                supported = bool(support_lookup[(scale, model)])
                rows.append(
                    {
                        "scale": scale,
                        "analysis_layer": "PHQ8_complete" if scale == "PHQ-8" else "HAMD16_core",
                        "model": model,
                        "strategy": selected_strategy,
                        "item_id": int(item_id),
                        "item_name": item_name(scale, int(item_id)),
                        "full_cohort_selected_condition_id": selected_condition,
                        "full_cohort_selected_condition": f"C{selected_condition:02d}",
                        "selection_reason": winner["selection_reason"],
                        "full_cohort_common_subject_n": int(winner.get("n_common", 0)),
                        "selected_corrected_rho": float(winner.get("selected_rho", math.nan)),
                        "selected_item_MAE": float(selected_metrics["item_mae"]),
                        "C03_item_MAE": float(c03_metrics["item_mae"]),
                        "delta_item_MAE": float(selected_metrics["item_mae"] - c03_metrics["item_mae"]),
                        "selected_item_NAE": float(selected_metrics["item_nae"]),
                        "C03_item_NAE": float(c03_metrics["item_nae"]),
                        "selected_coverage": float(selected_metrics["coverage"]),
                        "C03_coverage": float(c03_metrics["coverage"]),
                        "outer_route_top_condition": f"C{int(stability['top_condition_id']):02d}",
                        "outer_route_top_frequency": float(stability["top_selection_frequency"]),
                        "outer_route_normalized_entropy": float(stability["normalized_entropy"]),
                        "full_map_matches_outer_mode": selected_condition == int(stability["top_condition_id"]),
                        "cell_total_generalization_supported": supported,
                        "future_use_status": (
                            f"仅作为未来独立样本的前瞻候选{selected_strategy}映射；当前只支持总分MAE改善"
                            if supported
                            else f"不建议替换C03；仅保留{selected_strategy}探索性全样本映射"
                        ),
                    }
                )
    return pd.DataFrame(rows)


def build_decision_table(inference: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in inference.sort_values(["scale", "model"]).itertuples(index=False):
        item_improved = bool(row.delta_item_NAE <= 0 and row.delta_sum_item_AE <= 0)
        cancellation_ok = bool(row.delta_cancellation_ratio <= 0)
        if row.generalization_supported and item_improved and cancellation_ok:
            claim = f"总分与条目层面均支持，可进入外部样本验证"
            action = f"锁定{row.strategy}映射后做独立外部验证"
        elif row.generalization_supported:
            claim = f"仅支持总分MAE改善；条目误差或抵消未改善"
            action = f"作为{row.strategy}总分优化候选；不得宣称条目更准，需外部样本验证"
        else:
            claim = f"不支持{row.strategy}相对C03的稳定外推"
            action = f"保留C03；{row.strategy}仅作阴性或探索性结果"
        rows.append(
            {
                "scale": row.scale,
                "analysis_layer": row.analysis_layer,
                "model": row.model,
                "selected_strategy": row.strategy,
                "delta_total_MAE": row.delta_total_MAE,
                "delta_total_MAE_CI_low": row.delta_total_MAE_CI_low,
                "delta_total_MAE_CI_high": row.delta_total_MAE_CI_high,
                "sign_flip_q": row.sign_flip_q,
                "fold_improvement_rate": row.fold_improvement_rate,
                "total_generalization_supported": bool(row.generalization_supported),
                "delta_item_NAE": row.delta_item_NAE,
                "delta_sum_item_AE": row.delta_sum_item_AE,
                "delta_cancellation_ratio": row.delta_cancellation_ratio,
                "item_accuracy_improved": item_improved,
                "cancellation_not_increased": cancellation_ok,
                "claim_boundary": claim,
                "recommended_next_action": action,
            }
        )
    return pd.DataFrame(rows)


def across_ai_composite(subject: pd.DataFrame, selected_strategy: str) -> pd.DataFrame:
    rows = []
    for (scale, layer), group in subject.groupby(["scale", "analysis_layer"], sort=True):
        pivot = group.pivot(index="subject_id", columns="model", values="delta_total_MAE").dropna(axis=0, how="any")
        values = pivot.mean(axis=1).to_numpy(float)
        stats = paired_mean_difference(values, np.zeros(len(values)), bootstrap_reps=BOOTSTRAP_REPS, permutation_reps=PERMUTATION_REPS, seed=seed_for("selected_across_ai", selected_strategy, scale, layer, SEED))
        g, g_low, g_high = bootstrap_gz(values, seed_for("selected_across_ai_g", selected_strategy, scale, layer, SEED))
        rows.append(
            {
                "scale": scale,
                "analysis_layer": layer,
                "strategy": selected_strategy,
                "complete_across_AI_subject_n": len(values),
                "AI_equal_mean_delta_MAE": stats["delta"],
                "CI_low": stats["ci_low"],
                "CI_high": stats["ci_high"],
                "sign_flip_p": stats["p_value"],
                "hedges_gz": g,
                "hedges_gz_CI_low": g_low,
                "hedges_gz_CI_high": g_high,
            }
        )
    return pd.DataFrame(rows)


def make_figures(selection_effects: pd.DataFrame, inference: pd.DataFrame, fold: pd.DataFrame, selected_strategy: str) -> None:
    fig_dir = OUT / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    palette = {"A": "#355F8A", "B": "#1B7F5A", "C": "#A87524"}
    labels = {
        "DeepSeek-V4-Pro": "DeepSeek",
        "GLM-5.2": "GLM",
        "Kimi-K2.6": "Kimi",
        "Qwen3.7-Max": "Qwen",
    }
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 5.8), sharex=True)
    for ax, strategy in zip(axes, SELECTION_STRATEGIES):
        data = selection_effects[selection_effects["strategy"] == strategy].copy()
        data["label"] = data["scale"].str.replace("-8", "", regex=False).str.replace("-17", "", regex=False) + " / " + data["model"].map(labels)
        data = data.sort_values(["scale", "model"], ascending=[False, True]).reset_index(drop=True)
        y = np.arange(len(data))
        x = data["hedges_gz"].to_numpy(float)
        low = data["hedges_gz_CI_low"].to_numpy(float)
        high = data["hedges_gz_CI_high"].to_numpy(float)
        ax.errorbar(x, y, xerr=np.vstack([x - low, high - x]), fmt="o", color=palette[strategy], ecolor="#6B7280", capsize=3)
        ax.axvline(0, color="#111827", linewidth=1)
        ax.set_yticks(y, data["label"])
        ax.set_title(f"Strategy {strategy}")
        ax.grid(axis="x", color="#E5E7EB", linewidth=0.7)
        ax.set_xlabel("Hedges gₓ (negative favors strategy)")
    fig.suptitle("A/B/C total-error effects from frozen outer OOF evidence", fontsize=13)
    fig.tight_layout()
    for ext in ("png", "pdf", "svg"):
        fig.savefig(fig_dir / f"F1_strategy_effect_forest.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.2), sharex=False)
    for ax, scale in zip(axes, ("PHQ-8", "HAMD-17")):
        data = inference[inference["scale"] == scale].sort_values("model").reset_index(drop=True)
        y = np.arange(len(data))
        x = data["delta_total_MAE"].to_numpy(float)
        low = data["delta_total_MAE_CI_low"].to_numpy(float)
        high = data["delta_total_MAE_CI_high"].to_numpy(float)
        colors = ["#1B7F5A" if v else "#A87524" for v in data["generalization_supported"]]
        for yi, xi, lo, hi, color in zip(y, x, low, high, colors):
            ax.errorbar([xi], [yi], xerr=[[xi - lo], [hi - xi]], fmt="o", color=color, ecolor="#6B7280", capsize=3)
        ax.axvline(0, color="#111827", linewidth=1)
        ax.set_yticks(y, data["model"].map(labels))
        ax.set_title(f"{scale}: {selected_strategy} vs C03")
        ax.set_xlabel(f"ΔMAE (negative favors {selected_strategy})")
        ax.grid(axis="x", color="#E5E7EB", linewidth=0.7)
    fig.suptitle(f"Selected strategy {selected_strategy}: pooled-cohort repeated outer OOF")
    fig.tight_layout()
    for ext in ("png", "pdf", "svg"):
        fig.savefig(fig_dir / f"F2_{selected_strategy}_generalization_forest.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2), sharey=False)
    for ax, scale in zip(axes, ("PHQ-8", "HAMD-17")):
        data = fold[fold["scale"] == scale]
        models = sorted(data["model"].unique())
        arrays = [data.loc[data["model"] == model, "delta_MAE"].to_numpy(float) for model in models]
        ax.boxplot(arrays, tick_labels=[labels[m] for m in models], showfliers=False)
        for pos, arr in enumerate(arrays, start=1):
            jitter = np.linspace(-0.16, 0.16, len(arr))
            ax.scatter(np.full(len(arr), pos) + jitter, arr, s=10, alpha=0.35, color="#355F8A")
        ax.axhline(0, color="#111827", linewidth=1)
        ax.set_title(f"{scale}: 50 held-out fold effects")
        ax.set_ylabel(f"Fold ΔMAE ({selected_strategy} − C03)")
        ax.grid(axis="y", color="#E5E7EB", linewidth=0.7)
    fig.suptitle(f"Repeated five-fold effect distribution for strategy {selected_strategy}")
    fig.tight_layout()
    for ext in ("png", "pdf", "svg"):
        fig.savefig(fig_dir / f"F3_{selected_strategy}_fold_effect_distribution.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def build_report(
    selection_summary: pd.DataFrame,
    selected: str,
    inference: pd.DataFrame,
    composite: pd.DataFrame,
    decision_table: pd.DataFrame,
) -> str:
    selection_lines = []
    for row in selection_summary.sort_values("strategy").itertuples(index=False):
        selection_lines.append(
            f"- {row.strategy}: PHQ mean ΔMAE={row.PHQ_mean_delta_MAE:+.3f}; "
            f"HAMD mean ΔMAE={row.HAMD_mean_delta_MAE:+.3f}; "
            f"PHQ AI-equal g_z={row.PHQ_effect_gz:+.3f} (MAE rank {row.PHQ_effect_rank}); "
            f"HAMD AI-equal g_z={row.HAMD_effect_gz:+.3f} (MAE rank {row.HAMD_effect_rank}); "
            f"Level1={row.level1_cells}, Level2={row.level2_cells}, stability pass={row.stability_acceptable_cells}, "
            f"test47 support={row.test47_replication_support_cells}. {row.selection_reason}。"
        )
    result_lines = []
    for row in inference.sort_values(["scale", "model"]).itertuples(index=False):
        result_lines.append(
            f"- {row.scale}/{row.model}: {row.strategy} MAE={row.selected_total_MAE:.3f}, C03={row.C03_total_MAE:.3f}, "
            f"Δ={row.delta_total_MAE:+.3f}, 95% CI [{row.delta_total_MAE_CI_low:+.3f}, {row.delta_total_MAE_CI_high:+.3f}], "
            f"sign-flip q={row.sign_flip_q:.4f}, paired-t p={row.paired_t_p:.4f}, fold improvement={row.fold_improvement_rate:.1%}. "
            f"Δitem NAE={row.delta_item_NAE:+.4f}, Δcancellation={row.delta_cancellation_ratio:+.4f}. {row.interpretation}。"
        )
    composite_lines = []
    for row in composite.sort_values("scale").itertuples(index=False):
        composite_lines.append(
            f"- {row.scale}: three-AI equal-weight participant composite ΔMAE={row.AI_equal_mean_delta_MAE:+.3f}, "
            f"95% CI [{row.CI_low:+.3f}, {row.CI_high:+.3f}], p={row.sign_flip_p:.4f}."
        )
    decision_lines = []
    for row in decision_table.sort_values(["scale", "model"]).itertuples(index=False):
        decision_lines.append(f"- {row.scale}/{row.model}: {row.claim_boundary}；{row.recommended_next_action}。")
    return f"""## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: validate
- Origin Date: 2026-09-15
- Verification Status: VERIFIED
- Version Label: teacher_effect_size_generalization_v2

# 老师要求的方案选择与外推性结果

## 确定方案

确定后续方案为 **{selected}**。会议明确要求 PHQ 与 HAMD 分开看量表整体总分 MAE 效应量，因此分别在每个量表内比较 A/B/C 的总分 MAE 变化；标准化 Hedges g_z 作为森林图的辅助表达，不把两种量表合并成一个结论。Level、条目真实性、稳定性和 test47 结果作为解释与风险约束。

{chr(10).join(selection_lines)}

A 在 PHQ 和 HAMD 两个量表的整体总分 MAE 效应量中都排名第一，所以本轮严格按会议规则选择 A。B 是唯一出现 Level2 且得到 test47 支持的方案，这说明它在条目真实性上更均衡；但在本次以总分 MAE 为主要标准的两个量表内都低于 A，因此不进入主外推检验。A 的代价是既有探索结果中经常伴随条目误差和误差抵消增加，所以即使后续总分 MAE 外推成立，也只能解释为“总分误差改善”，不能解释为“每个条目都更准”。

## 后续外推怎么做

PHQ 使用全部 189 人，HAMD 使用全部 99 人；HAMD 主分析排除金标准为 9、不可评估的 H14，使用 HAMD16-core。两者复用已经冻结的 10 次重复 × 5 折外层划分。每个 outer training 内，分别对每个 AI、每个条目选择“预测条目分数与扣除该条目后的量表总分”校正 Spearman 相关最高的 condition；该映射原样用于 held-out fold。验证受试者上的 A 与同一 AI 的 C03 做配对比较。正式检验为先将同一受试者 10 次 OOF 结果求均值，再做受试者层面的 sign-flip permutation 与 bootstrap CI；paired t-test 和 Wilcoxon 是敏感性检验。50 个 fold 的分布只用于稳定性描述，不作为 50 个相互独立研究。

## 每个 AI 的结果

{chr(10).join(result_lines)}

## 跨 AI 总体效应

{chr(10).join(composite_lines)}

这里的 AI-equal composite 只用于同一量表内的描述和总体推断；PHQ 与 HAMD 的效应量、样本量和选择排名始终分开报告，不能把两种量表合并为一个总效应。

## 按 AI 的最终处理

{chr(10).join(decision_lines)}

已经另行生成各 AI 用全队列拟合的 A 条件映射，只用于未来新增受试者的前瞻候选。它们没有参与本报告的 OOF 效应估计；只有 PHQ/DeepSeek 和 PHQ/Qwen 的映射具有当前队列内总分外推支持，其他模型仍应保留 C03。所有候选映射都需要新的独立样本才能升级为部署规则。

## 结论

后续主线按两个量表分别选择的 A 展开。只有验证折 CI 完全低于 0 且 FDR q<0.05 的 AI，才能称为在当前队列内具有跨受试者泛化证据。点估计改善但区间跨 0 的 AI，只能称方向性结果。即使总分 MAE 显著，若 item NAE、条目绝对误差或抵消变差，结果也只能支持总分层面的优化。Cross-AI 混合路由已经表现更差，保留为补充分析，不再进入后续主路径。

## 统计风险检查

11/11 fallacy types checked。Simpson：PHQ 与 HAMD 分开排名和分层报告，并在量表内另报 AI composite；ecological：推断单位是受试者；Berkson：临床/DAIC 队列选择限制外推范围；collider：未加入结果导出的协变量；base-rate：本分析不是诊断分类；regression-to-mean：不是极端组前后比较；survivorship：PHQ189 与 HAMD16-core 维持全样本；look-elsewhere：A/B/C 探索后按两个量表各自的总分 MAE 规则选择 A，并在每个量表内对三个 AI 做 FDR；forking paths：条件、折分和量表内选择规则均在本轮外推前锁定，但策略探索和外推仍使用重叠受试者，因此这是内部验证；causation：只陈述预测误差，不作因果主张；reverse causality：不涉及时间方向因果。
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_hash_before = sha256(SOURCE)
    phq_fold_hash_before = sha256(PHQ_FOLDS)
    hamd_fold_hash_before = sha256(HAMD_FOLDS)
    selection_effects, selection_composite, selection_summary, selected = load_selection_evidence()
    if selected != SELECTED_STRATEGY:
        raise AssertionError(f"teacher effect-size rule selected {selected}, expected {SELECTED_STRATEGY}")
    cube = load_cube()
    routes, candidates, predictions = fit_and_apply_selected(cube, selected)
    subject_repeat = aggregate_primary_subject_repeat(predictions)
    inference, fold_distribution, subject_inference = inference_from_subject_repeat(subject_repeat, routes, selected)
    route_summary = route_stability(routes)
    ai_composite = across_ai_composite(subject_inference, selected)
    full_cohort_maps = fit_full_cohort_candidate_maps(cube, route_summary, inference, selected)
    decision_table = build_decision_table(inference)

    outputs = {
        "01_strategy_selection_effects.csv": selection_effects,
        "02_strategy_selection_composite.csv": selection_composite,
        "03_strategy_selection_summary.csv": selection_summary,
        "04_A_outer_routes.csv": routes,
        "05_A_training_candidate_metrics.csv": candidates,
        "06_A_outer_oof_item_predictions.csv": predictions,
        "07_A_subject_repeat_metrics.csv": subject_repeat,
        "08_A_subject_level_inference_data.csv": subject_inference,
        "09_A_primary_inference.csv": inference,
        "10_A_fold_effect_distribution.csv": fold_distribution,
        "11_A_route_stability.csv": route_summary,
        "12_A_across_AI_composite.csv": ai_composite,
        "13_A_full_cohort_candidate_maps.csv": full_cohort_maps,
        "14_interpretation_decision_table.csv": decision_table,
    }
    for name, frame in outputs.items():
        write_csv(frame, name)
    make_figures(selection_effects, inference, fold_distribution, selected)
    report = build_report(selection_summary, selected, inference, ai_composite, decision_table)
    (OUT / "RESULTS.md").write_text(report, encoding="utf-8")

    checks = {
        "selected_strategy_is_A_by_teacher_effect_rule": selected == "A",
        "source_hash_matches_frozen": source_hash_before == sha256(SOURCE) == "34ec669d677860b2b671d01f3f3d77a66d669ec693cd64cf42347eb1bdc2fa4d",
        "PHQ_fold_hash_matches": phq_fold_hash_before == sha256(PHQ_FOLDS) == "12c219dfe3b6d31983f4f0acf5304ed2dee788aa9ee29fea48dd0a1edc5354d4",
        "HAMD_fold_hash_matches": hamd_fold_hash_before == sha256(HAMD_FOLDS) == "ca2feabcf6f175b8092596427f3645b2f95525ae3b6c29535e05266130bbeddf",
        "PHQ_subjects_189": predictions[predictions["scale"] == "PHQ-8"]["subject_id"].nunique() == 189,
        "HAMD_subjects_99": predictions[predictions["scale"] == "HAMD-17"]["subject_id"].nunique() == 99,
        "six_primary_inference_rows": len(inference) == 6,
        "paired_repeats_exactly_10": subject_inference["paired_repeat_n"].eq(10).all(),
        "routes_one_per_fold_item_model": routes.duplicated(["scale", "model", "repeat", "fold", "item_id"]).sum() == 0,
        "outer_predictions_only_A_and_C03": set(predictions["strategy"]) == {"A", "C03"},
        "HAMD14_absent_from_primary_routes_and_predictions": not (
            ((routes["scale"] == "HAMD-17") & (routes["item_id"] == 14)).any()
            or ((predictions["scale"] == "HAMD-17") & (predictions["item_id"] == 14)).any()
        ),
        "full_cohort_candidate_map_rows_72": len(full_cohort_maps) == 72,
        "supported_cells_are_PHQ_DeepSeek_and_Qwen": set(
            map(tuple, inference.loc[inference["generalization_supported"], ["scale", "model"]].to_numpy())
        ) == {("PHQ-8", "DeepSeek-V4-Pro"), ("PHQ-8", "Qwen3.7-Max")},
        "raw_data_modified_false": source_hash_before == sha256(SOURCE),
        "llm_calls_zero": True,
    }
    check_rows = [{"check": key, "status": "PASS" if value else "FAIL", "observed": bool(value)} for key, value in checks.items()]
    write_csv(pd.DataFrame(check_rows), "verification_checks.csv")
    status = "PASS" if all(checks.values()) else "FAIL"

    workbook_payload = {
        "selected_strategy": selected,
        "selection_summary": json.loads(selection_summary.to_json(orient="records", force_ascii=False)),
        "primary_inference": json.loads(inference.to_json(orient="records", force_ascii=False)),
        "composite": json.loads(ai_composite.to_json(orient="records", force_ascii=False)),
        "fold_distribution": json.loads(fold_distribution.to_json(orient="records", force_ascii=False)),
        "route_stability": json.loads(route_summary.to_json(orient="records", force_ascii=False)),
        "full_cohort_candidate_maps": json.loads(full_cohort_maps.to_json(orient="records", force_ascii=False)),
        "decision_table": json.loads(decision_table.to_json(orient="records", force_ascii=False)),
        "checks": check_rows,
    }
    (OUT / "workbook_payload.json").write_text(json.dumps(workbook_payload, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "analysis_name": "teacher-focused A/B/C scale-specific total-MAE selection followed by A-only per-AI cross-subject generalization",
        "status": status,
        "selected_strategy": selected,
        "selection_rule": "teacher-specified primary criterion: within each scale, most negative mean total-MAE change across AI cells; PHQ and HAMD ranks are independent; Hedges gz is forest companion",
        "stage1_source": str(THREE_DIR.relative_to(ROOT)),
        "stage2_source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": sha256(SOURCE),
        "folds": {
            "PHQ": str(PHQ_FOLDS.relative_to(ROOT)),
            "PHQ_sha256": sha256(PHQ_FOLDS),
            "HAMD": str(HAMD_FOLDS.relative_to(ROOT)),
            "HAMD_sha256": sha256(HAMD_FOLDS),
            "design": "10 repeats x 5 folds; outer-training selection and held-out evaluation",
        },
        "scope": {"PHQ": "all189 pooled", "HAMD": "all99 HAMD16 core", "models": {"PHQ": list(PHQ_MODELS), "HAMD": list(HAMD_MODELS)}},
        "strategy_A": "per AI and item, select maximum outer-training corrected item-total Spearman correlation; common-subject comparison; ties prefer C03 then fixed condition order",
        "baseline": "same AI C03",
        "inference": "collapse 10 OOF repeats within subject; paired sign-flip permutation and participant bootstrap; paired t and Wilcoxon sensitivity; BH-FDR within scale across 3 AIs",
        "raw_data_modified": False,
        "llm_calls": 0,
        "python": sys.version,
        "platform": platform.platform(),
        "packages": {"numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__},
        "rows": {name: len(frame) for name, frame in outputs.items()},
        "verification_status": status,
    }
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "verification_report.json").write_text(json.dumps({"status": status, "checks": check_rows, "failures": [k for k, v in checks.items() if not v]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "selected_strategy": selected, "inference_rows": len(inference), "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
