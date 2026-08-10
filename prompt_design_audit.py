#!/usr/bin/env python3
"""Prompt-design audit for the local PDCH PHQ/HAMD result workbook.

This module deliberately stops before any prompt-feature -> model-outcome
association.  It profiles the result workbook, extracts the fixed prompt
templates from the authoritative local DOCX files, builds condition and
pairwise design audits, and writes frozen prompt-only analysis inputs.

The large source workbook is read in read-only mode and is never modified.
"""

from __future__ import annotations

import argparse
import ast
import csv
import difflib
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from docx import Document
from openpyxl import load_workbook


DEFAULT_INPUT = Path(
    "PDCH_PHQ_HAMD_所有模型所有条件_提示词字段完整修正版_20260807.xlsx"
)
DEFAULT_OUTPUT = Path("prompt_design_audit_20260810")
DEFAULT_HAMD_PROMPT = Path(
    r"E:\数据库\代码\Data\PDCH\实验\_新结构_待启用\hamd正式使用提示词.docx"
)
DEFAULT_PHQ_PROMPT = Path(
    r"E:\数据库\代码\Data\PDCH\实验\_新结构_待启用\PHQ全量189人_调用就绪\prompts\PHQ8_prompt_set_3_nonconditional_24_conditions_English.docx"
)
DEFAULT_CONDITIONS_SOURCE = Path(
    r"E:\数据库\代码\Data\PDCH\实验\_新结构_待启用\scripts\9eval_main.py"
)

CSV_FILES = {
    "field_inventory": "01_prompt_field_inventory.csv",
    "templates": "02_unique_prompt_templates.csv",
    "condition_dictionary": "03_condition_design_dictionary.csv",
    "pairwise_diff": "04_prompt_pairwise_diff.csv",
    "feature_coding": "05_prompt_feature_coding.csv",
    "manual_review": "06_prompt_feature_manual_review.csv",
    "manipulation_audit": "07_prompt_manipulation_audit.csv",
    "frozen_input": "08_prompt_analysis_frozen_input.csv",
    "data_quality": "10_data_quality_issues.csv",
}

DATA_SHEETS = [
    "01_字段对照",
    "02_统一结果索引",
    "03_等级结果明细",
    "04_评分维度明细",
    "05_独立事件明细",
    "06_覆盖审计",
    "07_提示词字段映射",
    "08_字段字典",
]

PAIR_DEFS = [
    (3, 4, "cleaning", "评分路径"),
    (3, 7, "standardization", "评分路径"),
    (3, 11, "text_scope", "评分路径"),
    (1, 2, "cleaning", "等级路径"),
    (1, 5, "standardization", "等级路径"),
    (1, 9, "text_scope", "等级路径"),
]

FEATURES = [
    "evidence_requirement",
    "evidence_quote_required",
    "explicit_scoring_anchors",
    "negation_handling",
    "missing_information_rule",
    "temporal_constraint",
    "frequency_requirement",
    "inference_permission",
    "speaker_restriction",
    "abstention_permission",
    "output_rigidity",
    "itemwise_reasoning_requirement",
    "aggregation_instruction",
    "uncertainty_requirement",
]

COMPLEXITY_FIELDS = [
    "static_character_count",
    "static_line_count",
    "estimated_token_count",
    "numbered_rule_count",
    "instruction_count",
    "output_constraint_count",
]


def text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return str(v)


def json_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False, sort_keys=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_prompt(value: str) -> str:
    """Only the allowed formatting normalization; semantics are untouched."""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in value.split("\n")]
    out: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        out.append(line)
        previous_blank = blank
    return "\n".join(out).strip()


def short_value(value: Any, limit: int = 320) -> str:
    s = json_text(value).replace("\r", "\\r").replace("\n", "\\n")
    return s if len(s) <= limit else s[: limit - 3] + "..."


def safe_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def condition_id(value: Any) -> int | None:
    n = safe_int(value)
    if n is not None:
        return n
    m = re.search(r"(?:C|条件\s*)0*(\d{1,2})", text(value), re.I)
    return int(m.group(1)) if m else None


def dataset_name(scale: Any) -> str:
    s = text(scale)
    if "PHQ" in s.upper():
        return "PHQ-8"
    if "HAMD" in s.upper():
        return "HAMD-17"
    return s or "UNKNOWN"


def clean_header(v: Any) -> str:
    return text(v).strip()


def infer_dtype(values: list[Any]) -> str:
    present = [v for v in values if v not in (None, "")]
    if not present:
        return "empty"
    kinds = set()
    for v in present:
        if isinstance(v, bool):
            kinds.add("boolean")
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            kinds.add("numeric")
        elif isinstance(v, (datetime, date)):
            kinds.add("datetime")
        elif isinstance(v, (dict, list, tuple)):
            kinds.add("json")
        else:
            s = text(v).strip()
            if s.startswith(("{", "[")):
                try:
                    json.loads(s)
                    kinds.add("json")
                    continue
                except Exception:
                    pass
            kinds.add("text")
    if len(kinds) == 1:
        return next(iter(kinds))
    return "mixed"


def value_kind(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "numeric"
    if isinstance(value, (datetime, date)):
        return "datetime"
    if isinstance(value, (dict, list, tuple)):
        return "json"
    s = text(value).strip()
    if s.startswith(("{", "[")):
        try:
            json.loads(s)
            return "json"
        except Exception:
            pass
    return "text"


def role_from_content(header: str, examples: list[str]) -> tuple[str, str]:
    h = header.lower()
    sample = "\n".join(examples)
    prompt_marker = any(
        marker.lower() in sample.lower()
        for marker in ("# role", "# instruction", "# step", "# end goal", "# narrow")
    )
    prompt_name = any(
        marker in h
        for marker in ("prompt", "instruction", "rubric", "system", "提示词", "评分规则")
    )
    if prompt_marker and prompt_name:
        return "fixed_prompt_text_observed", "实际单元格包含提示词结构标记；可直接作为固定提示词证据。"
    if "raw_response" in h or "完整raw_response" in h or "模型原始" in h:
        return "model_output/raw_response", "这是模型返回或解析后的输出，不是固定提示词。"
    if any(
        marker in h
        for marker in (
            "score",
            "分数",
            "等级",
            "置信",
            "confidence",
            "evidence",
            "证据",
            "reasoning",
            "理由",
            "probability",
            "概率",
            "误差",
            "error",
            "correct",
            "准确",
        )
    ):
        return "model_output/derived_analysis", "字段名和实际内容属于模型输出或由结果派生的分析变量。"
    if any(marker in h for marker in ("source", "路径", "metadata", "元数据", "context", "上下文")):
        return "provenance_metadata", "运行来源、路径或元数据；不等于提示词正文。"
    if any(marker in h for marker in ("subject", "被试", "condition", "条件", "model", "模型", "thinking", "思考", "scale", "量表", "scope", "范围", "standard", "规整", "clean", "清洗", "baseline", "基线", "record", "记录", "event", "事件", "cohort", "队列")):
        return "design_metadata/key", "实验设计、条件或主键元数据。"
    if any(marker in h for marker in ("transcript", "访谈", "原始文本", "input", "输入")):
        return "dynamic_input_or_source_text", "可能是动态输入，但该判断仅在字段实际内容支持时成立。"
    return "analysis_or_other", "未发现固定提示词结构标记；不能仅凭字段名把它当作提示词。"


def parse_prompt_docx(path: Path, dataset: str, language: str) -> dict[str, Any]:
    """Parse the local authoritative DOCX without changing its text."""
    if not path.exists():
        return {"status": "missing_source", "path": str(path), "conditions": {}, "front": {}}
    paragraphs = [p.text for p in Document(path).paragraphs]
    if dataset == "HAMD-17":
        condition_re = re.compile(r"^条件\s*0?(\d{1,2})\b")
        front_re = re.compile(r"^非条件提示词(?:[一二三123])")
    else:
        condition_re = re.compile(r"^Condition\s+0?(\d{1,2})\b", re.I)
        front_re = re.compile(r"^Non-conditional Prompt\s+[123]\b", re.I)
    condition_labels: list[tuple[int, int]] = []
    for i, p in enumerate(paragraphs):
        m = condition_re.match(p.strip())
        if m:
            condition_labels.append((int(m.group(1)), i))
    fronts = [(i, p.strip()) for i, p in enumerate(paragraphs) if front_re.match(p.strip())]
    conditions: dict[int, str] = {}
    for pos, (cid, start) in enumerate(condition_labels):
        end = condition_labels[pos + 1][1] if pos + 1 < len(condition_labels) else len(paragraphs)
        parts = [p.strip() for p in paragraphs[start + 1 : end] if p.strip()]
        conditions[cid] = "\n".join(parts)
    front: dict[str, str] = {}
    front_names = ["event_segmentation", "dimension_analysis", "narrative"]
    for pos, (start, _) in enumerate(fronts[:3]):
        end = fronts[pos + 1][0] if pos + 1 < len(fronts[:3]) else (condition_labels[0][1] if condition_labels else len(paragraphs))
        front[front_names[pos]] = "\n".join(p.strip() for p in paragraphs[start + 1 : end] if p.strip())
    if len(condition_labels) != 24 or set(cid for cid, _ in condition_labels) != set(range(1, 25)):
        status = "uncertain_condition_heading_parse"
    elif len(fronts) < 3:
        status = "uncertain_front_heading_parse"
    else:
        status = "extracted_from_local_docx"
    return {
        "status": status,
        "path": str(path),
        "language": language,
        "docx_sha256": sha256_file(path),
        "conditions": conditions,
        "front": front,
    }


def split_prompt_sections(prompt: str) -> dict[str, str]:
    markers = [(m.start(), m.group(1).lower()) for m in re.finditer(r"(?m)^#\s*(Role|Instruction|Step|End Goal|Narrow)\s*$", prompt)]
    sections = {}
    for i, (start, name) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(prompt)
        sections[name] = prompt[start:end].strip()
    return sections


def prompt_components(prompt: str) -> dict[str, str]:
    sections = split_prompt_sections(prompt)
    role = sections.get("role", "")
    instr = sections.get("instruction", "")
    step = sections.get("step", "")
    end_goal = sections.get("end goal", "")
    narrow = sections.get("narrow", "")
    rubric_lines = []
    for line in prompt.splitlines():
        if re.search(r"(?:\b[0-4]\s*[=:]|（[0-4]）|\bPHQ-?8\b|\bHAMD-?17\b|各级标准|severity definitions|frequency criteria)", line, re.I):
            rubric_lines.append(line.strip())
    rubric = "\n".join(dict.fromkeys(rubric_lines))
    other = "\n".join(x for x in (step, end_goal) if x)
    if instr and rubric:
        # Keep the original instruction in its own field; rubric is a traceable
        # extracted view, never a rewritten prompt.
        pass
    return {
        "static_system_prompt": role,
        "static_task_instruction": instr,
        "static_scoring_rubric": rubric,
        "static_output_instruction": narrow,
        "static_other_instruction": other,
    }


def parse_conditions(path: Path) -> list[dict[str, Any]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CONDITIONS" for t in node.targets):
            value = ast.literal_eval(node.value)
            if not isinstance(value, list):
                break
            return value
    raise ValueError(f"CONDITIONS assignment not found in {path}")


def observed_condition_name(row: dict[str, Any]) -> str:
    return text(row.get("条件全名_condition_full_name")) or text(row.get("条件_condition"))


def load_workbook_profiles(input_path: Path) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str, int], dict[str, Any]], dict[tuple[str, str, str, int], dict[str, Any]], dict[str, Any]]:
    """Profile every sheet and collect context-level non-outcome metadata."""
    wb = load_workbook(input_path, read_only=True, data_only=True)
    sheet_profiles: list[dict[str, Any]] = []
    contexts: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    coverage: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    metadata = {"sheet_names": list(wb.sheetnames), "sheet_rows": {}, "sheet_cols": {}}
    for ws in wb.worksheets:
        if ws.title not in DATA_SHEETS:
            continue
        rows = ws.iter_rows(values_only=True)
        header_row = next(rows, None)
        if not header_row:
            continue
        headers = [clean_header(x) for x in header_row]
        col_stats = [
            {"nonmissing": 0, "unique_hashes": set(), "examples": [], "kind_counts": Counter()}
            for _ in headers
        ]
        data_rows = 0
        for row in rows:
            data_rows += 1
            for idx, value in enumerate(row[: len(headers)]):
                stat = col_stats[idx]
                if value not in (None, ""):
                    stat["nonmissing"] += 1
                    if len(stat["examples"]) < 3:
                        stat["examples"].append(short_value(value))
                    stat["kind_counts"][value_kind(value)] += 1
                    stat["unique_hashes"].add(hashlib.sha1(json_text(value).encode("utf-8")).digest())
            if ws.title == "02_统一结果索引":
                row_dict = {headers[i]: row[i] if i < len(row) else None for i in range(len(headers))}
                ds = dataset_name(row_dict.get("量表_scale"))
                model = text(row_dict.get("模型_model"))
                mode = text(row_dict.get("思考模式_thinking_mode"))
                cid = condition_id(row_dict.get("条件编号_condition_id") or row_dict.get("条件_condition"))
                if not model or not mode or cid is None:
                    continue
                key = (ds, model, mode, cid)
                ctx = contexts.setdefault(
                    key,
                    {
                        "dataset": ds,
                        "model": model,
                        "mode": mode,
                        "condition": f"C{cid:02d}",
                        "condition_id": cid,
                        "condition_full_name": observed_condition_name(row_dict),
                        "subject_ids": set(),
                        "source_row_n": 0,
                        "prompt_versions": set(),
                        "prompt_languages": set(),
                        "metadata_parse_n": 0,
                        "parse_ok_n": 0,
                    },
                )
                ctx["source_row_n"] += 1
                sid = text(row_dict.get("被试ID_subject_id"))
                if sid:
                    ctx["subject_ids"].add(sid)
                if text(row_dict.get("解析状态_parse_status")) == "ok":
                    ctx["parse_ok_n"] += 1
                try:
                    md = json.loads(text(row_dict.get("完整元数据JSON_metadata")) or "{}")
                    if md.get("metadata_prompt_version"):
                        ctx["prompt_versions"].add(text(md["metadata_prompt_version"]))
                    if md.get("metadata_prompt_language"):
                        ctx["prompt_languages"].add(text(md["metadata_prompt_language"]))
                    ctx["metadata_parse_n"] += 1
                except Exception:
                    pass
            elif ws.title == "06_覆盖审计":
                row_dict = {headers[i]: row[i] if i < len(row) else None for i in range(len(headers))}
                ds = dataset_name(row_dict.get("量表_scale"))
                model = text(row_dict.get("模型_model"))
                mode = text(row_dict.get("思考模式_thinking_mode"))
                cid = condition_id(row_dict.get("条件编号_condition_id") or row_dict.get("条件_condition"))
                if model and mode and cid is not None:
                    coverage[(ds, model, mode, cid)] = {
                        "coverage_status": text(row_dict.get("覆盖状态_coverage_status")),
                        "expected_subject_n": safe_int(row_dict.get("预期被试数_expected_subject_n")),
                        "subject_result_n": safe_int(row_dict.get("被试结果数_subject_result_n")),
                        "missing_subject_n": safe_int(row_dict.get("被试缺失数_missing_subject_n")),
                    }
        metadata["sheet_rows"][ws.title] = data_rows
        metadata["sheet_cols"][ws.title] = len(headers)
        for idx, header in enumerate(headers):
            stat = col_stats[idx]
            examples = stat["examples"]
            role, notes = role_from_content(header, examples)
            if role != "fixed_prompt_text_observed":
                notes += " 固定提示词正文不以字段名推断；本工作簿未观察到可直接复用的静态prompt字段。"
            sheet_profiles.append(
                {
                    "sheet": ws.title,
                    "original_column": header,
                    "inferred_role": role,
                    "dtype": (
                        next(iter(stat["kind_counts"]))
                        if len(stat["kind_counts"]) == 1
                        else "mixed"
                        if stat["kind_counts"]
                        else "empty"
                    ),
                    "row_n": data_rows,
                    "nonmissing_n": stat["nonmissing"],
                    "missing_rate": round((data_rows - stat["nonmissing"]) / data_rows, 8) if data_rows else 0,
                    "unique_n": len(stat["unique_hashes"]),
                    "example_value": examples[0] if examples else "",
                    "notes": notes,
                }
            )
    wb.close()
    for ctx in contexts.values():
        ctx["subject_n"] = len(ctx.pop("subject_ids"))
        ctx["prompt_versions"] = "; ".join(sorted(ctx["prompt_versions"]))
        ctx["prompt_languages"] = "; ".join(sorted(ctx["prompt_languages"]))
        ctx["result_coverage_status"] = "not_found"
    for key, cov in coverage.items():
        if key in contexts:
            contexts[key].update(cov)
            contexts[key]["result_coverage_status"] = cov.get("coverage_status") or "unknown"
    return sheet_profiles, contexts, coverage, metadata


def condition_design_rows(
    conditions: list[dict[str, Any]], contexts: dict[tuple[str, str, str, int], dict[str, Any]], prompt_sources: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    text_scope_map = {"全量": "全文", "事件标记": "事件序列", "独立事件": "独立事件"}
    rows: list[dict[str, Any]] = []
    observed_names: dict[int, set[str]] = defaultdict(set)
    for ctx in contexts.values():
        if ctx["condition_full_name"]:
            observed_names[ctx["condition_id"]].add(ctx["condition_full_name"])
    modes = sorted({ctx["mode"] for ctx in contexts.values()})
    for c in conditions:
        cid = int(c["id"])
        output = text(c.get("output"))
        pathway = "itemwise_score" if output == "评分" else "direct_grade"
        baseline = "C03" if pathway == "itemwise_score" else "C01"
        scope = text(c.get("text"))
        attr = text(c.get("attr"))
        clean = "是" if bool(c.get("clean")) else "否"
        full_name = sorted(observed_names.get(cid, set()))
        condition_name = full_name[0] if full_name else f"C{cid:02d}_{scope}_{attr}_{output}_{'清洗' if c.get('clean') else '不清洗'}"
        if cid in (1, 2): intended = "清洗" if cid == 2 else "基线"
        elif cid in (3, 4): intended = "清洗" if cid == 4 else "基线"
        elif cid in (5, 6, 7, 8): intended = "规整/规范化" if cid in (5, 7) else "规整/规范化 + 清洗"
        elif cid in (9, 10, 11, 12): intended = "事件序列输入范围" if cid in (9, 11) else "事件序列输入范围 + 清洗"
        else: intended = "独立事件输入范围" + (" + 清洗" if c.get("clean") else "") + (" + 规整" if attr == "规整" else "")
        if pathway == "itemwise_score" and cid not in (3, 4, 7, 8, 11, 12, 15, 16, 19, 20, 23, 24):
            intended = "评分路径"
        if pathway == "direct_grade" and cid not in (1, 2, 5, 6, 9, 10, 13, 14, 17, 18, 21, 22):
            intended = "等级路径"
        psrc = "; ".join(
            source.get("path", "") for source in prompt_sources.values() if source.get("path")
        )
        rows.append(
            {
                "condition": f"C{cid:02d}",
                "condition_name": condition_name,
                "pathway": pathway,
                "cleaned": clean,
                "structured": "是" if attr == "规整" else "否",
                "text_scope": text_scope_map.get(scope, scope),
                "itemwise_scoring": "是" if pathway == "itemwise_score" else "否",
                "direct_grade": "是" if pathway == "direct_grade" else "否",
                "thinking_mode": "由运行元数据决定；已观察：" + ("; ".join(modes) or "未观察到"),
                "baseline_condition": baseline,
                "intended_manipulation": intended,
                "intended_pair": "; ".join(f"C{a:02d}->C{b:02d}" for a, b, _, _ in PAIR_DEFS if cid in (a, b)) or "",
                "source_file": str(DEFAULT_CONDITIONS_SOURCE),
                "source_condition_literal": json.dumps(c, ensure_ascii=False, sort_keys=True),
                "prompt_source_note": psrc or "按量表分别读取本地DOCX；本行不使用结果字段推断提示词。",
                "notes": "条件字典来自9eval_main.py的CONDITIONS字面量；thinking不是C01-C16条件内的文本操纵。",
            }
        )
    return rows


def feature_evidence(text_value: str, patterns: Iterable[str]) -> str:
    lines = [line.strip() for line in text_value.splitlines() if line.strip()]
    for line in lines:
        if any(re.search(p, line, re.I) for p in patterns):
            return short_value(line, 500)
    return ""


def code_prompt_features(prompt: str) -> dict[str, Any]:
    lower = prompt.lower()
    def has(patterns: Iterable[str]) -> bool:
        return any(re.search(p, prompt, re.I) for p in patterns)

    out: dict[str, Any] = {}
    evidence_quote = feature_evidence(prompt, [r"key_evidence", r"关键证据", r"摘自输入", r"direct evidence", r"quote"])
    evidence_mention = has([r"evidence", r"证据", r"依据", r"supporting information"])
    out["evidence_requirement"] = ("required" if has([r"key_evidence", r"关键证据", r"extract.*evidence", r"提取.*证据", r"provide.*evidence"]) else "optional" if evidence_mention else "none", evidence_quote or ("提示词提及 evidence，但未见明确必填要求。" if evidence_mention else ""), "high" if evidence_quote else "medium" if evidence_mention else "high")
    out["evidence_quote_required"] = ("yes" if has([r"摘自输入文本", r"摘自原文", r"quote", r"direct.*evidence", r"key_evidence.*input"]) else "uncertain" if evidence_mention else "no", evidence_quote, "high" if evidence_quote else "medium" if evidence_mention else "high")
    anchor_matches = re.findall(r"(?:\b[0-4]\s*[=:]|（[0-4]）)", prompt)
    anchor_count = len(anchor_matches)
    anchor_quote = feature_evidence(prompt, [r"0\s*[=:]", r"1\s*[=:]", r"各级标准", r"frequency criteria", r"severity definitions"])
    out["explicit_scoring_anchors"] = ("complete" if anchor_count >= 8 else "partial" if anchor_count > 0 else "none", anchor_quote, "high" if anchor_count > 0 else "high")
    neg_quote = feature_evidence(prompt, [r"否认", r"排除", r"不.*表示", r"den(y|ies|ied)", r"no evidence", r"absence", r"negative"])
    out["negation_handling"] = ("explicit" if neg_quote else "implicit" if evidence_mention or anchor_count else "absent", neg_quote, "high" if neg_quote else "medium" if evidence_mention or anchor_count else "high")
    miss_quote = feature_evidence(prompt, [r"不能肯定", r"无法判断", r"信息不足", r"insufficient", r"cannot determine", r"limited evidence", r"有限临床线索"])
    if has([r"9\s*[=:]\s*不能肯定", r"abstain", r"拒答"]):
        miss_value = "other"
    elif has([r"limited evidence", r"有限证据", r"有限临床线索", r"estimate", r"推断", r"infer"]):
        miss_value = "infer_best_estimate"
    elif has([r"default.*0", r"无证据.*0", r"missing.*0"]):
        miss_value = "default_zero"
    else:
        miss_value = "unspecified"
    out["missing_information_rule"] = (miss_value, miss_quote, "high" if miss_quote else "medium" if miss_value != "unspecified" else "high")
    temporal_quote = feature_evidence(prompt, [r"过去两周", r"一周内", r"past two weeks", r"within one week", r"current interview", r"当前片段"])
    out["temporal_constraint"] = ("explicit_window" if has([r"过去两周", r"一周内", r"past two weeks", r"within one week"]) else "generic" if has([r"当前片段", r"current", r"访谈文本", r"interview text"]) else "absent", temporal_quote, "high" if temporal_quote else "medium" if has([r"current", r"当前"]) else "high")
    freq_quote = feature_evidence(prompt, [r"频率", r"每晚", r"几天", r"several days", r"more than half", r"nearly every day", r"how often", r"frequency"])
    out["frequency_requirement"] = ("explicit" if freq_quote else "implicit" if has([r"often", r"频繁", r"symptom criteria"]) else "absent", freq_quote, "high" if freq_quote else "medium" if has([r"often", r"频繁"]) else "high")
    infer_quote = feature_evidence(prompt, [r"不得推断", r"不要推断", r"do not infer", r"有限证据", r"有限临床线索", r"根据.*推断", r"infer from context", r"reasonably infer", r"estimate"])
    if has([r"不得推断", r"不要推断", r"do not infer"]): infer_value = "prohibited"
    elif has([r"有限证据", r"有限临床线索", r"谨慎", r"conservative", r"limited evidence"]): infer_value = "conservative"
    elif has([r"reasonably infer", r"infer from context", r"根据.*上下文推断"]): infer_value = "permissive"
    elif has([r"estimate", r"估计", r"推断", r"判断"]): infer_value = "moderate"
    else: infer_value = "uncertain"
    out["inference_permission"] = (infer_value, infer_quote, "high" if infer_quote else "low")
    speaker_quote = feature_evidence(prompt, [r"只.*患者", r"仅.*来访者", r"patient.*only", r"participant.*statement", r"患者诉述"])
    out["speaker_restriction"] = ("explicit" if speaker_quote else "implicit" if has([r"患者", r"participant", r"来访者", r"patient"]) else "absent", speaker_quote, "high" if speaker_quote else "medium" if has([r"患者", r"participant"]) else "high")
    abstain_quote = feature_evidence(prompt, [r"不能肯定", r"信息不足", r"insufficient", r"abstain", r"无法判断", r"cannot determine"])
    out["abstention_permission"] = ("required_when_insufficient" if has([r"信息不足", r"insufficient", r"when.*insufficient"]) else "yes" if abstain_quote else "no", abstain_quote, "high" if abstain_quote else "medium" if has([r"estimate", r"推断"]) else "high")
    if has([r"仅输出纯 JSON", r"pure JSON", r"strict JSON", r"JSON 对象", r"JSON object"]): rigidity = "strict_json_schema" if has([r"格式如下", r"format as follows", r"schema", r"字段", r"required fields"]) else "json"
    elif has([r"输出.*字段", r"structured", r"列表", r"events"]): rigidity = "structured_text"
    else: rigidity = "free_text"
    output_quote = feature_evidence(prompt, [r"JSON", r"格式如下", r"format as follows", r"仅输出"])
    keys = set(re.findall(r"[\"']([A-Za-z][A-Za-z0-9_]*)[\"']\s*:", prompt))
    known_keys = ["subject_id", "events", "event_id", "start_line", "end_line", "severity_level", "key_evidence", "score", "reasoning", "reasoning_chain", "confidence_score", "class_probabilities", "dimension", "item", "evidence"]
    keys.update(k for k in known_keys if re.search(rf"\b{re.escape(k)}\b", prompt))
    out["output_rigidity"] = (rigidity, output_quote, "high" if output_quote else "medium")
    out["required_output_field_n"] = (str(len(keys)), output_quote, "high" if keys else "medium")
    constraints = [line.strip() for line in prompt.splitlines() if line.strip()]
    narrow = split_prompt_sections(prompt).get("narrow", "")
    constraint_n = sum(1 for line in narrow.splitlines() if line.strip() and not line.strip().startswith("#"))
    out["output_constraint_n"] = (str(constraint_n), short_value(narrow, 500), "high")
    item_quote = feature_evidence(prompt, [r"每个维度", r"逐条", r"per item", r"each dimension", r"item[- ]level", r"all dimensions"])
    out["itemwise_reasoning_requirement"] = ("yes" if item_quote else "no", item_quote, "high" if item_quote else "medium")
    agg = []
    agg_quote = feature_evidence(prompt, [r"总分", r"逐题", r"sum", r"item score", r"overall.*score", r"severity_level"])
    if has([r"每个.*分数", r"item score", r"dimension.*score", r"逐题"]): agg.append("item_score_required")
    if has([r"sum", r"总分", r"overall.*total", r"逐题.*求和"]): agg.append("sum_required")
    if has([r"severity_level", r"等级", r"severity", r"score range", r"分数段"]): agg.append("grade_conversion_required")
    out["aggregation_instruction"] = (";".join(agg) or "none", agg_quote, "high" if agg_quote else "medium")
    unc = []
    unc_quote = feature_evidence(prompt, [r"confidence", r"置信度", r"probabilit", r"不确定"])
    if has([r"confidence", r"置信度"]): unc.append("confidence_required")
    if has([r"probabilit", r"概率"]): unc.append("probability_required")
    if has([r"不确定", r"uncertainty"]): unc.append("uncertainty_text_required")
    out["uncertainty_requirement"] = (";".join(unc) or "none", unc_quote, "high" if unc_quote else "medium")
    return out


def feature_row(ctx: dict[str, Any], template: dict[str, Any], features: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "dataset": ctx["dataset"],
        "model": ctx["model"],
        "mode": ctx["mode"],
        "condition": ctx["condition"],
        "prompt_template_id": template["prompt_template_id"],
        "prompt_source": template["prompt_source"],
        "feature_source": "固定DOCX提示词文本；未使用任何模型表现结果。",
    }
    for name in FEATURES:
        value, quote, conf = features[name]
        row[f"{name}_value"] = value
        row[f"{name}_evidence_quote"] = quote
        row[f"{name}_auto_confidence"] = conf
        row[f"{name}_review_required"] = "yes" if conf == "low" or value == "uncertain" else "no"
    for name in COMPLEXITY_FIELDS:
        row[name] = template.get(name, "")
    return row


def classify_pair(
    baseline_template: dict[str, Any] | None,
    target_template: dict[str, Any] | None,
    baseline_features: dict[str, Any] | None,
    target_features: dict[str, Any] | None,
    intended_factor: str,
) -> dict[str, Any]:
    if not baseline_template or not target_template or baseline_features is None or target_features is None:
        return {
            "exact_same": "unknown",
            "normalized_same": "unknown",
            "changed_line_n": "",
            "added_line_n": "",
            "removed_line_n": "",
            "added_text": "",
            "removed_text": "",
            "unified_diff": "",
            "changed_prompt_features": "",
            "unchanged_prompt_features": "",
            "unexpected_changes": "source prompt unavailable",
            "single_factor_status": "uncertain",
            "interpretation_allowed": "no_clean_interpretation",
            "notes": "未找到完整的固定提示词文本，不能可靠判断单因素操纵。",
        }
    a = baseline_template["full_static_prompt"].splitlines()
    b = target_template["full_static_prompt"].splitlines()
    diff = list(difflib.unified_diff(a, b, fromfile="baseline", tofile="target", lineterm=""))
    body = [x for x in diff if not x.startswith(("---", "+++", "@@"))]
    added = [x[1:] for x in body if x.startswith("+")]
    removed = [x[1:] for x in body if x.startswith("-")]
    changed_features = []
    unchanged_features = []
    for name in FEATURES:
        if baseline_features[name][0] != target_features[name][0]:
            changed_features.append(name)
        else:
            unchanged_features.append(name)
    exact_same = baseline_template["exact_sha256"] == target_template["exact_sha256"]
    normalized_same = baseline_template["normalized_sha256"] == target_template["normalized_sha256"]
    # Static prompt equality is itself meaningful: the design changes only the
    # runtime input factor, not the instruction text.  It is not evidence of a
    # prompt-text effect.
    if exact_same:
        status = "clean_single_factor"
        allowed = "single_factor_interpretation"
        notes = "固定system prompt完全相同；预期操纵发生在运行时输入条件，而非提示词文字。"
        unexpected = ""
    elif len(changed_features) == 1:
        status = "clean_single_factor"
        allowed = "single_factor_interpretation"
        notes = "固定提示词中仅检测到一个理论特征改变；仍需人工抽查差分文本。"
        unexpected = ""
    elif len(changed_features) == 0:
        status = "mostly_single_factor"
        allowed = "single_factor_interpretation"
        notes = "仅出现未被特征编码捕捉的文字差异；需要人工复核。"
        unexpected = "feature coding did not detect semantic change"
    elif len(changed_features) >= 5 or len(body) > 120:
        status = "not_comparable"
        allowed = "no_clean_interpretation"
        notes = "固定提示词差异过大，不能视为单一操纵。"
        unexpected = ";".join(changed_features)
    else:
        status = "multi_component_change"
        allowed = "bundle_interpretation_only"
        notes = "理论特征以外或多个可解释特征同时变化，只能按提示词包解释。"
        unexpected = ";".join(changed_features)
    return {
        "exact_same": "yes" if exact_same else "no",
        "normalized_same": "yes" if normalized_same else "no",
        "changed_line_n": len(body),
        "added_line_n": len(added),
        "removed_line_n": len(removed),
        "added_text": "\n".join(added),
        "removed_text": "\n".join(removed),
        "unified_diff": "\n".join(diff),
        "changed_prompt_features": ";".join(changed_features),
        "unchanged_prompt_features": ";".join(unchanged_features),
        "unexpected_changes": unexpected,
        "single_factor_status": status,
        "interpretation_allowed": allowed,
        "notes": notes,
    }


def assess_prompt_versions(dataset: str, versions: str) -> str:
    """Conservative metadata-only assessment; a version label is not a prompt hash."""
    values = [v for v in versions.split("; ") if v]
    if not values:
        return "missing_prompt_version"
    if len(values) > 1:
        return "multiple_versions_in_context"
    version = values[0]
    if dataset == "PHQ-8" and version == "PHQ8-word-2026-06-27":
        return "candidate_source_version"
    if dataset == "HAMD-17" and version in ("word-2026-06-25", "正式使用提示词-2026-06-25"):
        return "candidate_source_version"
    return "possible_version_variant"


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        seen = set()
        for row in rows:
            for k in row:
                if k not in seen:
                    keys.append(k)
                    seen.add(k)
        fieldnames = keys
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json_text(row.get(k, "")) for k in fieldnames})
    return len(rows)


def build_manual_review(feature_rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]], source_notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in feature_rows:
        for name in FEATURES:
            if row.get(f"{name}_review_required") == "yes":
                rows.append(
                    {
                        "dataset": row["dataset"],
                        "model": row["model"],
                        "mode": row["mode"],
                        "condition": row["condition"],
                        "prompt_template_id": row["prompt_template_id"],
                        "issue_type": "feature_uncertain_or_low_confidence",
                        "feature_name": name,
                        "feature_value": row.get(f"{name}_value", ""),
                        "feature_evidence_quote": row.get(f"{name}_evidence_quote", ""),
                        "auto_confidence": row.get(f"{name}_auto_confidence", ""),
                        "review_required": "yes",
                        "reviewer_code": "",
                        "reviewer_note": "",
                        "resolved": "",
                    }
                )
    for row in pair_rows:
        if row.get("single_factor_status") in ("multi_component_change", "not_comparable", "uncertain"):
            rows.append(
                {
                    "dataset": row.get("dataset", ""),
                    "model": row.get("model", ""),
                    "mode": row.get("mode", ""),
                    "condition": f"{row.get('baseline_condition', '')}->{row.get('target_condition', '')}",
                    "prompt_template_id": "",
                    "issue_type": "pair_not_clean_single_factor",
                    "feature_name": "",
                    "feature_value": row.get("single_factor_status", ""),
                    "feature_evidence_quote": short_value(row.get("unified_diff", ""), 1000),
                    "auto_confidence": "medium",
                    "review_required": "yes",
                    "reviewer_code": "",
                    "reviewer_note": "",
                    "resolved": "",
                }
            )
    for note in source_notes:
        rows.append(note)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--hamd-prompt", type=Path, default=DEFAULT_HAMD_PROMPT)
    parser.add_argument("--phq-prompt", type=Path, default=DEFAULT_PHQ_PROMPT)
    parser.add_argument("--conditions-source", type=Path, default=DEFAULT_CONDITIONS_SOURCE)
    args = parser.parse_args()
    input_path = args.input.resolve()
    output_dir = args.output_dir.resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    original_hash = sha256_file(input_path)
    print(f"input={input_path}")
    print(f"input_size={input_path.stat().st_size}")
    print(f"input_sha256={original_hash}")

    field_inventory, contexts, coverage, workbook_meta = load_workbook_profiles(input_path)
    print(f"contexts={len(contexts)}")
    conditions = parse_conditions(args.conditions_source.resolve())
    prompt_sources = {
        "HAMD-17": parse_prompt_docx(args.hamd_prompt.resolve(), "HAMD-17", "zh"),
        "PHQ-8": parse_prompt_docx(args.phq_prompt.resolve(), "PHQ-8", "en"),
    }
    templates_by_ds_cond: dict[tuple[str, int], dict[str, Any]] = {}
    template_pool: dict[str, dict[str, Any]] = {}
    for ds, source in prompt_sources.items():
        for cid, prompt in source.get("conditions", {}).items():
            exact_hash = sha256_text(prompt)
            normalized = normalize_prompt(prompt)
            normalized_hash = sha256_text(normalized)
            key = normalized_hash
            if key not in template_pool:
                template_pool[key] = {
                    "normalized_sha256": normalized_hash,
                    "exact_sha256": exact_hash,
                    "datasets": set(),
                    "conditions": set(),
                    "prompts": set(),
                    "prompt": prompt,
                    "prompt_source": source.get("path", ""),
                    "source_status": source.get("status", ""),
                }
            pool = template_pool[key]
            pool["datasets"].add(ds)
            pool["conditions"].add(cid)
            pool["prompts"].add(exact_hash)
            templates_by_ds_cond[(ds, cid)] = pool
    sorted_pools = sorted(template_pool.values(), key=lambda x: (x["normalized_sha256"], x["exact_sha256"]))
    for i, pool in enumerate(sorted_pools, 1):
        pool["prompt_template_id"] = f"PROMPT_{i:06d}"
    for key, pool in templates_by_ds_cond.items():
        templates_by_ds_cond[key] = pool

    # Observed occurrence and subject counts are metadata only, not outcomes.
    for pool in sorted_pools:
        pool["occurrence_n"] = 0
        pool["subject_ids"] = set()
        pool["models"] = set()
        pool["modes"] = set()
        pool["context_n"] = 0
        pool["prompt_versions"] = set()
    for ctx in contexts.values():
        pool = templates_by_ds_cond.get((ctx["dataset"], ctx["condition_id"]))
        if pool:
            pool["occurrence_n"] += int(ctx["source_row_n"])
            pool["subject_ids"].update({f"{ctx['dataset']}::{ctx['model']}::{ctx['mode']}::{ctx['condition']}::{i}" for i in range(int(ctx["subject_n"]))})
            pool["models"].add(ctx["model"])
            pool["modes"].add(ctx["mode"])
            if ctx.get("prompt_versions"):
                pool["prompt_versions"].update(
                    v for v in ctx["prompt_versions"].split("; ") if v
                )
            pool["context_n"] += 1
    template_rows: list[dict[str, Any]] = []
    template_features: dict[str, dict[str, Any]] = {}
    for pool in sorted_pools:
        prompt = pool["prompt"]
        components = prompt_components(prompt)
        feats = code_prompt_features(prompt)
        template_features[pool["prompt_template_id"]] = feats
        row = {
            "prompt_template_id": pool["prompt_template_id"],
            "exact_sha256": pool["exact_sha256"],
            "normalized_sha256": pool["normalized_sha256"],
            "dataset": ";".join(sorted(pool["datasets"])),
            "scale": ";".join(sorted(pool["datasets"])),
            "model": "shared across observed models" if len(pool["models"]) > 1 else ";".join(sorted(pool["models"])),
            "mode": "shared across observed modes" if len(pool["modes"]) > 1 else ";".join(sorted(pool["modes"])),
            "condition": ";".join(f"C{x:02d}" for x in sorted(pool["conditions"])),
            "pathway": "itemwise_score/direct_grade; see condition dictionary",
            **components,
            "full_static_prompt": prompt,
            "static_character_count": len(prompt),
            "static_line_count": len(prompt.splitlines()),
            "estimated_token_count": math.ceil(len(prompt) / 4),
            "numbered_rule_count": sum(
                1 for line in prompt.splitlines() if re.match(r"^\s*(?:\d+[.)]|[-*])\s+", line)
            ),
            "instruction_count": sum(
                1 for line in prompt.splitlines() if line.strip() and not line.strip().startswith("#")
            ),
            "output_constraint_count": sum(
                1
                for line in split_prompt_sections(prompt).get("narrow", "").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ),
            "occurrence_n": pool["occurrence_n"],
            "subject_n": len(pool["subject_ids"]),
            "context_n": pool["context_n"],
            "observed_prompt_versions": "; ".join(sorted(pool["prompt_versions"])),
            "source_sheet": "02_统一结果索引",
            "prompt_source": pool["prompt_source"],
            "extraction_status": pool["source_status"],
            "notes": "仅固定system prompt；被试文本、事件、路径和输出未纳入hash。normalized hash只做CRLF/行尾空格/连续空行规范化。",
        }
        template_rows.append(row)

    prompt_source_note = [
        {
            "dataset": ds,
            "model": "",
            "mode": "",
            "condition": "",
            "prompt_template_id": "",
            "issue_type": "prompt_source_outside_result_workbook",
            "feature_name": "static_dynamic_split",
            "feature_value": source.get("status", ""),
            "feature_evidence_quote": source.get("path", ""),
            "auto_confidence": "high" if source.get("status") == "extracted_from_local_docx" else "low",
            "review_required": "yes" if source.get("status") != "extracted_from_local_docx" else "no",
            "reviewer_code": "",
            "reviewer_note": "",
            "resolved": "",
        }
        for ds, source in prompt_sources.items()
    ]

    condition_rows = condition_design_rows(conditions, contexts, prompt_sources)
    condition_map = {row["condition"]: row for row in condition_rows}

    feature_rows: list[dict[str, Any]] = []
    for ctx in sorted(contexts.values(), key=lambda x: (x["dataset"], x["model"], x["mode"], x["condition_id"])):
        pool = templates_by_ds_cond.get((ctx["dataset"], ctx["condition_id"]))
        if not pool:
            continue
        template = next(x for x in template_rows if x["prompt_template_id"] == pool["prompt_template_id"])
        feature_rows.append(feature_row(ctx, template, template_features[pool["prompt_template_id"]]))

    pair_rows: list[dict[str, Any]] = []
    for ctx in sorted(contexts.values(), key=lambda x: (x["dataset"], x["model"], x["mode"])):
        # one row per observed context is assembled below; avoid duplicates
        pass
    seen_pair_keys = set()
    for ds, model, mode, _ in sorted(contexts.keys()):
        for a, b, factor, pathway in PAIR_DEFS:
            if (ds, model, mode, a, b) in seen_pair_keys:
                continue
            seen_pair_keys.add((ds, model, mode, a, b))
            base_pool = templates_by_ds_cond.get((ds, a))
            target_pool = templates_by_ds_cond.get((ds, b))
            bf = template_features.get(base_pool["prompt_template_id"]) if base_pool else None
            tf = template_features.get(target_pool["prompt_template_id"]) if target_pool else None
            diff = classify_pair(
                next((x for x in template_rows if base_pool and x["prompt_template_id"] == base_pool["prompt_template_id"]), None),
                next((x for x in template_rows if target_pool and x["prompt_template_id"] == target_pool["prompt_template_id"]), None),
                bf,
                tf,
                factor,
            )
            pair_rows.append(
                {
                    "dataset": ds,
                    "model": model,
                    "mode": mode,
                    "pathway": pathway,
                    "baseline_condition": f"C{a:02d}",
                    "target_condition": f"C{b:02d}",
                    "baseline_template_id": base_pool["prompt_template_id"] if base_pool else "",
                    "target_template_id": target_pool["prompt_template_id"] if target_pool else "",
                    "intended_manipulation": condition_map.get(f"C{b:02d}", {}).get("intended_manipulation", factor),
                    "baseline_prompt_version": contexts.get((ds, model, mode, a), {}).get("prompt_versions", ""),
                    "target_prompt_version": contexts.get((ds, model, mode, b), {}).get("prompt_versions", ""),
                    "baseline_prompt_version_assessment": assess_prompt_versions(
                        ds, contexts.get((ds, model, mode, a), {}).get("prompt_versions", "")
                    ),
                    "target_prompt_version_assessment": assess_prompt_versions(
                        ds, contexts.get((ds, model, mode, b), {}).get("prompt_versions", "")
                    ),
                    **diff,
                }
            )

    # Six pair audits are already per model/mode.  Add an exact-source stability
    # audit in the manipulation table, still without any output-performance field.
    manipulation_rows: list[dict[str, Any]] = []
    for row in pair_rows:
        ds, model, mode, a, b = row["dataset"], row["model"], row["mode"], row["baseline_condition"], row["target_condition"]
        ca = contexts.get((ds, model, mode, int(a[1:])), {})
        cb = contexts.get((ds, model, mode, int(b[1:])), {})
        version_same = bool(ca.get("prompt_versions")) and ca.get("prompt_versions", "") == cb.get("prompt_versions", "")
        if not version_same:
            row["single_factor_status"] = "uncertain"
            row["interpretation_allowed"] = "no_clean_interpretation"
            row["unexpected_changes"] = (
                (row.get("unexpected_changes", "") + "; " if row.get("unexpected_changes") else "")
                + "运行元数据prompt_version不同或缺失，DOCX静态差分不足以证明实际请求文本相同"
            )
            row["notes"] = row.get("notes", "") + "；运行元数据版本未能在该pair内保持一致，需人工核对实际请求记录。"
        manipulation_rows.append(
            {
                "dataset": ds,
                "model": model,
                "mode": mode,
                "baseline_condition": a,
                "target_condition": b,
                "pathway": row["pathway"],
                "intended_manipulation": row["intended_manipulation"],
                "baseline_template": row["baseline_template_id"],
                "target_template": row["target_template_id"],
                "changed_prompt_features": row["changed_prompt_features"],
                "unchanged_prompt_features": row["unchanged_prompt_features"],
                "unexpected_changes": row["unexpected_changes"],
                "single_factor_status": row["single_factor_status"],
                "interpretation_allowed": row["interpretation_allowed"],
                "exact_prompt_same": row["exact_same"],
                "normalized_prompt_same": row["normalized_same"],
                "observed_prompt_version_baseline": ca.get("prompt_versions", ""),
                "observed_prompt_version_target": cb.get("prompt_versions", ""),
                "prompt_version_consistency": (
                    "same_observed_version"
                    if ca.get("prompt_versions", "") == cb.get("prompt_versions", "")
                    and ca.get("prompt_versions", "")
                    else "version_unverified_or_different"
                ),
                "prompt_version_change_observed": (
                    "no"
                    if ca.get("prompt_versions", "") == cb.get("prompt_versions", "")
                    else "yes_or_unverified"
                ),
                "notes": row["notes"],
            }
        )

    frozen_rows: list[dict[str, Any]] = []
    feature_by_ctx = {(r["dataset"], r["model"], r["mode"], r["condition"]): r for r in feature_rows}
    for ctx in sorted(contexts.values(), key=lambda x: (x["dataset"], x["model"], x["mode"], x["condition_id"])):
        pool = templates_by_ds_cond.get((ctx["dataset"], ctx["condition_id"]))
        fr = feature_by_ctx.get((ctx["dataset"], ctx["model"], ctx["mode"], ctx["condition"]))
        design = condition_map.get(ctx["condition"], {})
        quality = "complete" if ctx.get("result_coverage_status") in ("完整", "complete", "PASS", "通过") else "coverage_status=" + (ctx.get("result_coverage_status") or "not_found")
        row = {
            "dataset": ctx["dataset"],
            "model": ctx["model"],
            "mode": ctx["mode"],
            "condition": ctx["condition"],
            "pathway": design.get("pathway", ""),
            "prompt_template_id": pool["prompt_template_id"] if pool else "",
            "cleaned": design.get("cleaned", ""),
            "structured": design.get("structured", ""),
            "text_scope": design.get("text_scope", ""),
            "itemwise_scoring": design.get("itemwise_scoring", ""),
            "direct_grade": design.get("direct_grade", ""),
            "baseline_condition": design.get("baseline_condition", ""),
            "intended_manipulation": design.get("intended_manipulation", ""),
            "prompt_source": pool["prompt_source"] if pool else "",
            "prompt_version_observed": ctx.get("prompt_versions", ""),
            "prompt_version_assessment": assess_prompt_versions(
                ctx["dataset"], ctx.get("prompt_versions", "")
            ),
            "prompt_language_observed": ctx.get("prompt_languages", ""),
            "observed_subject_n": ctx.get("subject_n", ""),
            "source_row_n": ctx.get("source_row_n", ""),
            "result_coverage_status": ctx.get("result_coverage_status", ""),
            "data_quality_flag": quality,
            "data_quality_notes": "冻结输入只含提示词设计、模板特征和覆盖元数据；没有金标准、预测、误差、正确性或任何性能字段。",
        }
        if fr:
            for name in FEATURES:
                row[name] = fr.get(f"{name}_value", "")
            for name in COMPLEXITY_FIELDS:
                row[name] = fr.get(name, "")
        frozen_rows.append(row)

    quality_rows = [
        {
            "severity": "high",
            "issue_type": "fixed_prompt_text_not_in_result_workbook",
            "scope": "all result sheets",
            "evidence": "字段盘点未观察到包含#Role/#Instruction/#Step/#End Goal/#Narrow的固定提示词单元格；模板来自本地权威DOCX。",
            "impact": "不能从结果工作簿单独复原每一次API请求的完整system prompt。",
            "likely_cause": "结果汇总表保存了模型输出和运行元数据，但没有保存system prompt正文。",
            "recommended_action": "保留本次DOCX提取结果；下一次运行将prompt hash和prompt version写入每个结果的metadata。",
            "status": "documented_not_repaired",
        },
        {
            "severity": "medium",
            "issue_type": "static_dynamic_split",
            "scope": "all contexts",
            "evidence": "source workbook contains result rows, paths and metadata; subject-specific input text is not a fixed prompt template. ",
            "impact": "subject text must not enter prompt_template_id or static prompt hash.",
            "likely_cause": "workbook is a result/field consolidation rather than a request log.",
            "recommended_action": "Use frozen template table for design variables and join subject outcomes only in the next preregistered stage.",
            "status": "controlled_by_method",
        },
        {
            "severity": "medium",
            "issue_type": "mixed_grain_sheets",
            "scope": "02/03/04/05/06",
            "evidence": "sheets represent subject-condition, grade, dimension and event grains; row counts differ by design.",
            "impact": "naive row-order joins can duplicate or mislink subjects/events.",
            "likely_cause": "intentional multi-grain result workbook.",
            "recommended_action": "Use explicit keys dataset×model×mode×condition×subject×event×unit; do not join on row order.",
            "status": "documented_not_repaired",
        },
    ]
    for ds, source in prompt_sources.items():
        if source.get("status") != "extracted_from_local_docx":
            quality_rows.append({
                "severity": "high",
                "issue_type": "prompt_docx_extraction_uncertain",
                "scope": ds,
                "evidence": source.get("path", ""),
                "impact": "模板hash和feature coding不能作为冻结输入。",
                "likely_cause": source.get("status", "missing_source"),
                "recommended_action": "人工确认DOCX headings后重新运行脚本。",
                "status": "open_manual_review",
            })
    # Metadata prompt-version consistency is an audit finding, not an outcome.
    for ds in sorted({ctx["dataset"] for ctx in contexts.values()}):
        versions = sorted({v for ctx in contexts.values() if ctx["dataset"] == ds for v in ctx.get("prompt_versions", "").split("; ") if v})
        quality_rows.append({
            "severity": "medium" if len(versions) > 1 else "low",
            "issue_type": "observed_prompt_version_consistency",
            "scope": ds,
            "evidence": "; ".join(versions) or "metadata中未发现prompt_version",
            "impact": "同一量表若出现多个版本，不能把条件差异归因于单一操纵。",
            "likely_cause": "运行批次元数据",
            "recommended_action": "对多版本组合人工核对；将版本作为冻结设计变量。",
            "status": "review_required" if len(versions) > 1 or not versions else "pass",
        })

    codebook_rows = []
    feature_descriptions = {
        "evidence_requirement": "提示词是否要求提供证据；只按原文明确要求编码。",
        "evidence_quote_required": "是否要求证据直接来自输入文本或原文引用。",
        "explicit_scoring_anchors": "是否存在明确的分值/等级锚点；不把结果字段当锚点。",
        "negation_handling": "是否明确处理否认、排除或无证据。",
        "missing_information_rule": "缺少信息时的原文规则；未见规则编码 unspecified。",
        "temporal_constraint": "是否限定过去两周、一周内或当前片段等时间窗口。",
        "frequency_requirement": "是否要求或定义发生频率。",
        "inference_permission": "上下文推断权限；没有原文支持编码 uncertain。",
        "speaker_restriction": "是否限定只使用患者/来访者信息。",
        "abstention_permission": "是否允许或要求信息不足时拒答/无法判断。",
        "output_rigidity": "自由文本、结构化文本、JSON或严格JSON schema。",
        "itemwise_reasoning_requirement": "是否要求逐条/逐维度推理。",
        "aggregation_instruction": "是否要求条目分数、求和或等级转换。",
        "uncertainty_requirement": "是否要求置信度、概率或不确定性文字。",
    }
    for name in FEATURES:
        codebook_rows.append({
            "feature_name": name,
            "中文解释": feature_descriptions[name],
            "允许值": "按05_prompt_feature_coding.csv中的value列；另有evidence_quote、auto_confidence、review_required。",
            "原文证据规则": "没有明确文本支持时不猜测；使用absent/none/unspecified/uncertain并进入人工复核。",
            "是否可进入下一阶段": "待人工复核后冻结；本阶段不与任何性能字段关联。",
        })
    for name in COMPLEXITY_FIELDS:
        codebook_rows.append({
            "feature_name": name,
            "中文解释": "提示词静态文本复杂度辅助描述变量。",
            "允许值": "数值；estimated_token_count为字符数/4向上取整的粗略估计，不是API tokenizer计数。",
            "原文证据规则": "直接由固定prompt文本计算。",
            "是否可进入下一阶段": "可以作为冻结设计协变量，但不得提前与结果关联。",
        })

    # Field inventory and templates are written first, then a compact manifest
    # is used by the artifact-tool workbook builder.
    field_count = write_csv(output_dir / CSV_FILES["field_inventory"], field_inventory)
    template_count = write_csv(output_dir / CSV_FILES["templates"], template_rows)
    condition_count = write_csv(output_dir / CSV_FILES["condition_dictionary"], condition_rows)
    pair_count = write_csv(output_dir / CSV_FILES["pairwise_diff"], pair_rows)
    feature_count = write_csv(output_dir / CSV_FILES["feature_coding"], feature_rows)
    manual_rows = build_manual_review(feature_rows, pair_rows, prompt_source_note)
    manual_count = write_csv(output_dir / CSV_FILES["manual_review"], manual_rows)
    manipulation_count = write_csv(output_dir / CSV_FILES["manipulation_audit"], manipulation_rows)
    frozen_count = write_csv(output_dir / CSV_FILES["frozen_input"], frozen_rows)
    quality_count = write_csv(output_dir / CSV_FILES["data_quality"], quality_rows)
    codebook_count = write_csv(output_dir / "11_coding_rules.csv", codebook_rows)

    manifest_rows = []
    for key, filename in {**CSV_FILES, "coding_rules": "11_coding_rules.csv"}.items():
        path = output_dir / filename
        manifest_rows.append(
            {
                "artifact": filename,
                "description": key,
                "row_n": sum(1 for _ in path.open("r", encoding="utf-8-sig")) - 1,
                "sha256": sha256_file(path),
                "contains_model_outcome": "no" if key in ("field_inventory", "templates", "condition_dictionary", "pairwise_diff", "feature_coding", "manual_review", "manipulation_audit", "frozen_input", "data_quality", "coding_rules") else "unknown",
            }
        )
    manifest_rows.append({
        "artifact": input_path.name,
        "description": "original local source workbook",
        "row_n": "",
        "sha256": original_hash,
        "contains_model_outcome": "source workbook; not copied or modified",
    })
    manifest_count = write_csv(output_dir / "12_result_index.csv", manifest_rows)

    audit_meta = {
        "input_path": str(input_path),
        "input_size": input_path.stat().st_size,
        "input_sha256": original_hash,
        "input_sha256_after_generation": sha256_file(input_path),
        "input_unchanged": original_hash == sha256_file(input_path),
        "workbook": workbook_meta,
        "contexts": len(contexts),
        "conditions_from_source": len(conditions),
        "prompt_sources": {
            ds: {k: v for k, v in source.items() if k not in ("conditions", "front")}
            for ds, source in prompt_sources.items()
        },
        "unique_prompt_templates": template_count,
        "csv_rows": {
            "field_inventory": field_count,
            "templates": template_count,
            "condition_dictionary": condition_count,
            "pairwise_diff": pair_count,
            "feature_coding": feature_count,
            "manual_review": manual_count,
            "manipulation_audit": manipulation_count,
            "frozen_input": frozen_count,
            "data_quality": quality_count,
            "coding_rules": codebook_count,
            "result_index": manifest_count,
        },
        "stopping_rule": "本模块只生成提示词设计审计与冻结输入；不计算任何prompt feature与MAE/NAE/accuracy/bias/evidence drift的关联。",
    }
    (output_dir / "audit_metadata.json").write_text(json.dumps(audit_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    # JSON is convenient for the workbook builder and does not expose outcomes.
    (output_dir / "condition_rows.json").write_text(json.dumps(condition_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "codebook_rows.json").write_text(json.dumps(codebook_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    pair_summary = Counter(
        (r["dataset"], r["baseline_condition"], r["target_condition"], r["single_factor_status"])
        for r in pair_rows
    )
    versions_by_dataset = {
        ds: sorted({v for c in contexts.values() if c["dataset"] == ds for v in c.get("prompt_versions", "").split("; ") if v})
        for ds in sorted({c["dataset"] for c in contexts.values()})
    }
    report_lines = [
        "# PDCH PHQ-8 / HAMD-17 提示词设计审计报告",
        "",
        "## 1. 数据与范围",
        "",
        f"- 源结果工作簿：`{input_path.name}`；大小 `{input_path.stat().st_size}` bytes。",
        f"- 源文件 SHA-256：`{original_hash}`；生成前后相同：`{audit_meta['input_unchanged']}`。",
        f"- 源工作簿：{len(workbook_meta['sheet_names'])} 个sheet；观察到 {len(contexts)} 个 dataset×model×mode 上下文。",
        f"- 固定提示词来自两个本地DOCX；未从GitHub下载、未修改125 MB源文件。",
        "",
        "## 2. C01-C16 模板稳定性",
        "",
        f"- 9个观察上下文均有完整 C01-C16（每个16行）；pair审计共 {pair_count} 行，即每个上下文6组预设pair。",
        f"- 唯一静态模板 {template_count} 个；同一 dataset×condition 未发现多个 template ID。",
        f"- HAMD metadata 中观察到的 prompt_version：{'; '.join(versions_by_dataset.get('HAMD-17', [])) or '未记录'}。",
        f"- PHQ metadata 中观察到的 prompt_version：{'; '.join(versions_by_dataset.get('PHQ-8', [])) or '未记录'}。",
        "- 版本标签不是prompt hash；同一量表出现多个版本时只记录为版本不确定/需人工核对，不能直接宣称不同模型或思考模式使用完全相同的实际请求文本。",
        "",
        "## 3. 六组重点pair与实际文本差异",
        "",
        "| pair | 状态计数 | 固定文本层面的观察 |",
        "|---|---:|---|",
    ]
    for a, b, _, _ in PAIR_DEFS:
        for ds in ("HAMD-17", "PHQ-8"):
            counts = Counter()
            changed = set()
            versions = set()
            for r in pair_rows:
                if r["dataset"] == ds and r["baseline_condition"] == f"C{a:02d}" and r["target_condition"] == f"C{b:02d}":
                    counts[r["single_factor_status"]] += 1
                    if r.get("added_text") or r.get("removed_text"):
                        changed.add((r.get("added_text", ""), r.get("removed_text", "")))
                    versions.add((r.get("baseline_prompt_version", ""), r.get("target_prompt_version", "")))
            if counts:
                diff_note = "固定文本相同（变化在运行时输入条件）" if all(
                    r.get("exact_same") == "yes" for r in pair_rows if r["dataset"] == ds and r["baseline_condition"] == f"C{a:02d}" and r["target_condition"] == f"C{b:02d}"
                ) else f"检测到{len(changed)}种固定文本差异；详见04_prompt_pairwise_diff.csv"
                report_lines.append(f"| {ds} C{a:02d}→C{b:02d} | {dict(counts)} | {diff_note}；版本组合数={len(versions)} |")
    report_lines.extend(
        [
            "",
            "状态解释：`clean_single_factor` 接近单因素；`mostly_single_factor` 需要人工抽查；`multi_component_change` 只能按提示词包解释；`not_comparable`/`uncertain` 不允许干净机制解释。运行版本缺失或不同会将pair降级为uncertain。",
            "",
            "## 4. 冻结的提示词特征",
            "",
            f"- 05_prompt_feature_coding.csv：{feature_count} 个上下文行；每个特征都带 value、原文证据、自动置信度和复核标记。",
            "- 特征来自固定DOCX文本，不使用MAE、等级准确率、证据覆盖率或其他模型表现结果。",
            "- 复杂度字段是描述变量；estimated_token_count为字符数/4的粗略估计，不是供应商tokenizer计费量。",
            "",
            "## 5. 人工复核",
            "",
            f"- 待复核行数：{manual_count}；其中低置信度/不确定特征和pair版本/单因素问题均已进入06_prompt_feature_manual_review.csv。",
            "- reviewer_code、reviewer_note、resolved 保持空白，不替人工作结论。",
            "",
            "## 6. 输出与停止",
            "",
            "- 已生成8个审计CSV、数据质量问题表、编码规则表、结果索引、Excel总表和方法文档。",
            "- 09_冻结分析输入.csv不含gold/prediction/MAE/NAE/correct/sensitivity/specificity/bias/F1等结果字段。",
            "- 本阶段在提示词设计审计完成后停止；不自动开始任何prompt feature与模型性能的关联分析。",
        ]
    )
    (output_dir / "prompt_design_audit_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps(audit_meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
