#!/usr/bin/env python3
"""Code-first trace of the PDCH C01-C16 experiment design.

This module is intentionally separate from the result/performance audit.  It
does not calculate MAE, accuracy, or any other model-outcome statistic.  The
authoritative objects are the local runner source, the prompt builder, the
runtime manifests, and the prompt DOCX files actually referenced by those
manifests.  It produces a compact, reproducible trace that answers:

    condition -> input path logic -> prompt builder/source -> prompt version
    -> scoring pathway -> thinking-mode control

The large source workbook is inspected for provenance only and is never
modified or copied.
"""

from __future__ import annotations

import argparse
import ast
import csv
import difflib
import hashlib
import importlib.util
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


PAIR_DEFS = [
    (3, 4, "cleaning", "清洗"),
    (3, 7, "standardization", "规整"),
    (3, 11, "text_scope", "文本范围"),
    (1, 2, "cleaning", "清洗"),
    (1, 5, "standardization", "规整"),
    (1, 9, "text_scope", "文本范围"),
]

TEXT_NAME = {"全量": "全文", "事件标记": "事件序列", "独立事件": "独立事件"}

FEATURE_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "evidence_requirement": [
        ("required", r"(?i)(key_evidence|evidence_quote|原文证据|原文引用).{0,80}(必须|required|摘自|direct quote)"),
        ("optional", r"(?i)(key_evidence|evidence_quote|evidence)"),
    ],
    "evidence_quote_required": [("yes", r"(?i)(必须摘自|摘自原文|direct quote|quote from the input|原文引用)"), ("no", r"(?!)")],
    "explicit_scoring_anchors": [("complete", r"(?i)(HAMD-?17|PHQ-?8).{0,200}(?:0\s*=|0=).{0,500}(?:1\s*=|1=)"), ("partial", r"(?i)(评分|score|severity|严重度|分级)"), ("none", r"(?!)")],
    # "无/没有" inside a scale rubric is not, by itself, a negation rule;
    # require an instruction-level negation/denial cue.
    "negation_handling": [("explicit", r"(?i)(否认|不计入|negat(?:ion|ive)|denies|no symptom|negation handling)"), ("absent", r"(?!)")],
    "missing_information_rule": [("abstain_9", r"(?i)(score\s*(?:可|may|can)\s*(?:取|be)\s*9|取9|be 9|cannot determine|无法判断|不能肯定)"), ("infer_best_estimate", r"(?i)(best estimate|结合.*语境.*推断|结合.*片段.*推断|未直接提及.*推断|infer from context)"), ("unspecified", r"(?!)")],
    "temporal_constraint": [("explicit_window", r"(?i)(2\s*周|two\s*weeks|半小时|30\s*minutes|每晚|每周|last\s+\w+|过去\d+|within\s+\d+)"), ("generic", r"(?i)(时间|time|当前|current|近期|recent)"), ("absent", r"(?!)")],
    "frequency_requirement": [("explicit", r"(?i)(每天|几乎每天|每晚|频率|daily|nearly every day|every night|frequency)"), ("implicit", r"(?i)(持续|反复|often|recurrent|persistent)"), ("absent", r"(?!)")],
    "inference_permission": [("prohibited", r"(?i)(不得推断|禁止推断|do not infer|do not speculate|仅使用直接陈述|only direct statements)"), ("permissive", r"(?i)(合理推断|结合.*推断|可结合|infer from context|best estimate|may infer|reasonable inference)"), ("moderate", r"(?i)(基于.*线索|based on.*evidence|结合当前.*线索|from the input text)"), ("unspecified", r"(?!)")],
    "speaker_restriction": [("explicit", r"(?i)(只能使用.*(患者|来访者|participant|patient)|only use.*(participant|patient)|participant information only)"), ("absent", r"(?!)")],
    "abstention_permission": [("required_when_insufficient", r"(?i)(取9|be 9|cannot determine|无法判断|不能肯定)"), ("yes", r"(?i)(拒答|abstain|insufficient information)"), ("no", r"(?!)")],
    "output_rigidity": [("strict_json_schema", r"(?i)(仅输出纯 JSON|纯 JSON|only output.*JSON|strict JSON|格式如下|format as)"), ("structured_text", r"(?i)(自然段|paragraph|structured)"), ("free_text", r"(?!)")],
    "itemwise_reasoning_requirement": [("yes", r"(?i)(每个维度|each dimension|dimensions.*reasoning|reasoning.*confidence)"), ("no", r"(?!)")],
    "uncertainty_requirement": [("confidence_required", r"(?i)(confidence_score|置信度|confidence)"), ("probability_required", r"(?i)(class_probabilities|概率|probabilit)"), ("uncertainty_text_required", r"(?i)(reasoning_chain|不确定性|uncertainty)"), ("none", r"(?!)")],
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def normalize_prompt(value: str) -> str:
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


def short(value: Any, limit: int = 600) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def relative_path(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_assignment(tree: ast.AST, name: str) -> ast.AST:
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = list(getattr(node, "targets", [])) or [getattr(node, "target", None)]
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                return node.value
    raise ValueError(f"assignment {name!r} not found")


def parse_conditions(source_path: Path) -> tuple[list[dict[str, Any]], int]:
    source = read_text(source_path)
    tree = ast.parse(source, filename=str(source_path))
    value = find_assignment(tree, "CONDITIONS")
    conditions = ast.literal_eval(value)
    if not isinstance(conditions, list) or len(conditions) != 24:
        raise ValueError(f"Expected 24 CONDITIONS entries, got {len(conditions) if isinstance(conditions, list) else type(conditions)}")
    line = int(getattr(value, "lineno", 1))
    return conditions, line


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def parse_data_paths(source_path: Path) -> tuple[dict[str, dict[str, Any]], int]:
    source = read_text(source_path)
    tree = ast.parse(source, filename=str(source_path))
    value = find_assignment(tree, "DATA_PATHS")
    if not isinstance(value, ast.Dict):
        raise ValueError("DATA_PATHS is not a dict literal")
    result: dict[str, dict[str, Any]] = {}
    for key_node, value_node in zip(value.keys, value.values):
        key = _literal(key_node)
        if not isinstance(key, str) or not isinstance(value_node, ast.Dict):
            continue
        row: dict[str, Any] = {"data_path_key": key, "source_line": int(getattr(value_node, "lineno", 1))}
        for k, v in zip(value_node.keys, value_node.values):
            name = _literal(k)
            if not isinstance(name, str):
                continue
            if name in {"clean", "type"}:
                row[name] = _literal(v)
            elif name in {"path", "dir"}:
                row["path_kind"] = name
                row["path_expression"] = ast.unparse(v)
        result[key] = row
    return result, int(getattr(value, "lineno", 1))


def function_line(source_path: Path, name: str) -> int | None:
    tree = ast.parse(read_text(source_path), filename=str(source_path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return int(node.lineno)
    return None


def parse_docx(path: Path, language: str) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing_source", "path": str(path), "conditions": {}, "front": {}}
    try:
        from docx import Document
    except Exception as exc:  # pragma: no cover - environment-specific
        return {"status": "python_docx_unavailable", "path": str(path), "error": repr(exc), "conditions": {}, "front": {}}
    paragraphs = [p.text.strip() for p in Document(path).paragraphs]
    if language == "zh":
        condition_re = re.compile(r"^条件\s*0?(\d{1,2})\b")
        front_re = re.compile(r"^非条件提示词")
        front_names = ["event_segmentation", "dimension_analysis", "narrative"]
    else:
        condition_re = re.compile(r"^Condition\s+0?(\d{1,2})\b", re.I)
        front_re = re.compile(r"^Non-conditional Prompt\s+[123]\b", re.I)
        front_names = ["event_segmentation", "dimension_analysis", "narrative"]
    condition_labels = [(i, int(m.group(1))) for i, text in enumerate(paragraphs) if (m := condition_re.match(text))]
    front_labels = [(i, text) for i, text in enumerate(paragraphs) if front_re.match(text)]
    conditions: dict[int, str] = {}
    for position, (start, condition_id) in enumerate(condition_labels):
        end = condition_labels[position + 1][0] if position + 1 < len(condition_labels) else len(paragraphs)
        conditions[condition_id] = "\n".join(x for x in paragraphs[start + 1 : end] if x)
    front: dict[str, str] = {}
    first_condition = condition_labels[0][0] if condition_labels else len(paragraphs)
    for position, (start, _) in enumerate(front_labels[:3]):
        end = front_labels[position + 1][0] if position + 1 < len(front_labels[:3]) else first_condition
        front[front_names[position]] = "\n".join(x for x in paragraphs[start + 1 : end] if x)
    ok = len(condition_labels) == 24 and set(conditions) == set(range(1, 25)) and len(front_labels) >= 3
    return {
        "status": "extracted_from_docx" if ok else "uncertain_docx_parse",
        "path": str(path),
        "language": language,
        "docx_sha256": sha256_file(path),
        "condition_n": len(condition_labels),
        "front_n": len(front_labels),
        "conditions": conditions,
        "front": front,
    }


def load_code_builder(scripts_dir: Path):
    module_path = scripts_dir / "word_prompt_templates.py"
    previous = os.environ.pop("PDCH_PROMPT_DOCX", None)
    try:
        spec = importlib.util.spec_from_file_location("pdch_word_prompt_templates_code_trace", module_path)
        if spec is None or spec.loader is None:
            raise ImportError(module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is not None:
            os.environ["PDCH_PROMPT_DOCX"] = previous


def scan_workbook(path: Path) -> dict[str, Any]:
    before_hash = sha256_file(path)
    info: dict[str, Any] = {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256_before": before_hash,
        "is_actual_xlsx": path.read_bytes()[:4] == b"PK\x03\x04",
        "scan_status": "header_only",
        "sheet_n": None,
        "sheets": [],
    }
    try:
        # Reading every cell of the 125 MB workbook is unnecessary for a
        # code-trace audit and can take several minutes.  Read the XLSX
        # workbook metadata and worksheet dimensions directly from the ZIP
        # package instead.  The prior result-field audit remains the source
        # for detailed cell-level inventory.
        ns_main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        ns_rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        ns_pkg = "http://schemas.openxmlformats.org/package/2006/relationships"
        with zipfile.ZipFile(path) as archive:
            workbook_xml = ET.fromstring(archive.read("xl/workbook.xml"))
            rels_xml = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            rel_map = {
                rel.attrib.get("Id"): rel.attrib.get("Target", "")
                for rel in rels_xml.findall(f"{{{ns_pkg}}}Relationship")
            }
            for sheet in workbook_xml.findall(f"{{{ns_main}}}sheets/{{{ns_main}}}sheet"):
                name = sheet.attrib.get("name", "")
                rel_id = sheet.attrib.get(f"{{{ns_rel}}}id", "")
                target = rel_map.get(rel_id, "")
                target = target.lstrip("/")
                if not target.startswith("xl/"):
                    target = "xl/" + target
                if target not in archive.namelist():
                    continue
                # The dimension element is near the beginning of a worksheet
                # XML file.  Do not decompress and parse the entire sheet.
                with archive.open(target) as worksheet_file:
                    head = worksheet_file.read(2_000_000)
                dimension_match = re.search(rb"<dimension\b[^>]*\bref=['\"]([^'\"]+)", head)
                ref = dimension_match.group(1).decode("utf-8", errors="replace") if dimension_match else ""
                info["sheets"].append({"name": name, "dimension_ref": ref})
        info["scan_status"] = "zip_xml_dimensions"
        info["sheet_n"] = len(info["sheets"])
    except Exception as exc:
        info["scan_error"] = repr(exc)
    info["sha256_after"] = sha256_file(path)
    info["unchanged"] = info["sha256_before"] == info["sha256_after"]
    return info


def resolve_prompt_path(raw: str, project_root: Path) -> Path | None:
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.exists():
        return candidate.resolve()
    candidate = project_root / raw
    if candidate.exists():
        return candidate.resolve()
    # Manifest paths may contain a project-relative path.  Check the known
    # prompt locations explicitly; do not recursively scan the runs tree for
    # every manifest (there are many historical run folders).
    known = [
        project_root / "_新结构_待启用" / "PHQ数据" / candidate.name,
        project_root / "_新结构_待启用" / "PHQ行号数据" / candidate.name,
        project_root / "_新结构_待启用" / "PHQ全量189人_调用就绪" / "prompts" / candidate.name,
        project_root / "_新结构_待启用" / candidate.name,
    ]
    for path in known:
        if path.exists():
            return path.resolve()
    return None


def infer_dataset(manifest: dict[str, Any]) -> str:
    value = " ".join(str(manifest.get(k, "")) for k in ("dataset_source", "dataset_folder", "raw_dir", "prompt_docx"))
    if "PHQ" in value.upper():
        return "PHQ-8"
    if "HAMD" in value.upper() or "PDCH" in value.upper():
        return "HAMD-17"
    return "UNKNOWN"


def scan_run_manifests(project_root: Path) -> list[dict[str, Any]]:
    audit_root = project_root / "_新结构_待启用" / ".codex_audit"
    rows: list[dict[str, Any]] = []
    if not audit_root.exists():
        return rows
    for path in sorted(audit_root.glob("high_concurrency_repair_*/manifest.json")):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "prompt_version" not in manifest:
            continue
        dataset = infer_dataset(manifest)
        prompt_docx_raw = str(manifest.get("prompt_docx") or "")
        prompt_path = resolve_prompt_path(prompt_docx_raw, project_root) if prompt_docx_raw else None
        source_mode = "docx_override" if prompt_docx_raw else "code_builder"
        models = manifest.get("models") or []
        if isinstance(models, str):
            models = [models]
        rows.append({
            "manifest_path": str(path),
            "dataset": dataset,
            "dataset_source": manifest.get("dataset_source", ""),
            "dataset_folder": manifest.get("dataset_folder", ""),
            "run_variant": manifest.get("run_variant", ""),
            "created_at": manifest.get("created_at", ""),
            "prompt_version": manifest.get("prompt_version", ""),
            "prompt_language": manifest.get("prompt_language", ""),
            "prompt_docx_recorded": prompt_docx_raw,
            "prompt_docx_resolved": str(prompt_path) if prompt_path else "",
            "prompt_docx_sha256": sha256_file(prompt_path) if prompt_path else "",
            "source_mode": source_mode,
            "model_n": len(models),
            "models": ",".join(str(x) for x in models),
            "conditions": json_dump(manifest.get("conditions", "ALL")),
            "is_primary_run": "yes" if str(manifest.get("run_variant", "")) in {"", "thinking", "nothinking", "thinking_on_20260723", "thinking_on_20260724"} else "no",
        })
    return rows


def condition_name(cond: dict[str, Any]) -> str:
    return f"{int(cond['id']):02d}_{TEXT_NAME.get(cond['text'], cond['text'])}_{cond['attr']}_{cond['output']}_{'清洗' if cond['clean'] else '不清洗'}"


def pathway(cond: dict[str, Any]) -> str:
    return "itemwise_score" if cond["output"] == "评分" else "direct_grade"


def scope_name(value: str) -> str:
    return {"全量": "full_text", "事件标记": "event_sequence", "独立事件": "independent_event"}.get(value, value)


def intended_pair(cid: int) -> tuple[str, int | None, str]:
    mapping = {
        2: ("cleaning", 1, "C01→C02"), 4: ("cleaning", 3, "C03→C04"),
        5: ("standardization", 1, "C01→C05"), 7: ("standardization", 3, "C03→C07"),
        9: ("text_scope", 1, "C01→C09"), 11: ("text_scope", 3, "C03→C11"),
    }
    if cid in mapping:
        return mapping[cid]
    return ("multiple_factor_or_reference", None, "")


def get_path_logic(data_paths: dict[str, dict[str, Any]], cond: dict[str, Any]) -> dict[str, Any]:
    key = str(cond["C"]) + ("_clean" if cond.get("clean") else "")
    row = data_paths.get(key, {})
    expr = str(row.get("path_expression", ""))
    root_var = "RAW_DIR" if "RAW_DIR" in expr else "BASE_DIR"
    return {"data_path_key": key, "input_type": row.get("type", ""), "path_kind": row.get("path_kind", ""), "path_expression": expr, "input_root_variable": root_var, "data_path_source_line": row.get("source_line", "")}


def build_condition_rows(conditions: list[dict[str, Any]], data_paths: dict[str, dict[str, Any]], source_paths: dict[str, Path], run_rows: list[dict[str, Any]], project_root: Path, scripts_dir: Path) -> list[dict[str, Any]]:
    datasets = ["HAMD-17", "PHQ-8"]
    dataset_runs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in run_rows:
        if row["dataset"] in datasets:
            dataset_runs[row["dataset"]].append(row)
    rows: list[dict[str, Any]] = []
    condition_line = parse_conditions(scripts_dir / "9eval_main.py")[1]
    for dataset in datasets:
        runs = dataset_runs.get(dataset, [])
        modes = sorted({r["source_mode"] for r in runs})
        versions = sorted({str(r["prompt_version"]) for r in runs if r["prompt_version"]})
        for cond in conditions[:16]:
            cid = int(cond["id"])
            pair_factor, baseline, pair_label = intended_pair(cid)
            path_info = get_path_logic(data_paths, cond)
            actual_source = "docx_override" if dataset == "PHQ-8" else ("code_builder;docx_override" if "docx_override" in modes else "code_builder")
            rows.append({
                "dataset": dataset,
                "condition": f"C{cid:02d}",
                "condition_id": cid,
                "condition_name": condition_name(cond),
                "pathway": pathway(cond),
                "cleaned": "yes" if cond["clean"] else "no",
                "structured": "yes" if cond["attr"] == "规整" else "no",
                "text_scope": scope_name(cond["text"]),
                "itemwise_scoring": "yes" if cond["output"] == "评分" else "no",
                "direct_grade": "yes" if cond["output"] == "等级" else "no",
                "thinking_mode_control": "PDCH_ENABLE_THINKING; 9eval_main.py::_get_enable_thinking",
                "thinking_mode_is_condition_factor": "no",
                "baseline_condition": f"C{baseline:02d}" if baseline else "",
                "intended_manipulation": pair_factor,
                "intended_pair": pair_label,
                "input_code_key": path_info["data_path_key"],
                "input_type": path_info["input_type"],
                "input_root_variable": path_info["input_root_variable"],
                "input_path_kind": path_info["path_kind"],
                "input_path_expression": path_info["path_expression"],
                "output_directory_expression": "get_output_dir_name(cond) -> {id:02d}_{TEXT_NAME[text]}_{attr}_{output}_{clean/no-clean}",
                "output_directory_name": condition_name(cond),
                "prompt_builder_call": "9eval_main.py::build_system_prompt -> word_prompt_templates.py::build_condition_prompt",
                "prompt_override_hook": "word_prompt_templates.py::_PROMPT_DOCX -> prompt_docx_loader.load_prompt_docx",
                "runtime_prompt_source": actual_source,
                "observed_prompt_versions": ";".join(versions),
                "observed_run_manifest_n": len(runs),
                "conditions_source_file": relative_path(scripts_dir / "9eval_main.py", project_root),
                "conditions_source_line": condition_line,
                "data_paths_source_file": relative_path(scripts_dir / "9eval_main.py", project_root),
                "data_paths_source_line": path_info["data_path_source_line"],
                "prompt_builder_source_file": relative_path(scripts_dir / "word_prompt_templates.py", project_root),
                "prompt_builder_source_lines": "231-274",
                "dynamic_input_source_lines": "586-598; 748-772",
                "thinking_source_lines": "605-617; 665-674",
                "notes": "clean/structured/text_scope改变输入路径或输入描述；是否真正改变固定提示词由prompt_source_variant及pairwise diff单独核验。",
            })
    return rows


def prompt_id(prompt: str) -> str:
    return "PROMPT_" + hashlib.sha256(normalize_prompt(prompt).encode("utf-8")).hexdigest()[:12].upper()


def build_template_rows(variants: dict[str, dict[str, Any]], project_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant_id, variant in variants.items():
        for cid in range(1, 25):
            prompt = variant["prompts"].get(cid, "")
            if not prompt:
                continue
            normalized = normalize_prompt(prompt)
            rows.append({
                "prompt_source_variant": variant_id,
                "dataset": variant["dataset"],
                "condition": f"C{cid:02d}",
                "condition_id": cid,
                "prompt_template_id": prompt_id(prompt),
                "exact_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "normalized_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                "character_count": len(prompt),
                "line_count": len(prompt.splitlines()),
                "estimated_token_count": (len(prompt) + 3) // 4,
                "source_kind": variant["source_kind"],
                "source_file": variant["source_file"],
                "source_file_sha256": variant["source_file_sha256"],
                "extraction_status": variant["extraction_status"],
                "full_static_prompt": prompt,
            })
    return rows


def first_evidence(prompt: str, pattern: str) -> str:
    try:
        regex = re.compile(pattern)
    except re.error:
        return ""
    for line in prompt.splitlines():
        if regex.search(line):
            return short(line, 320)
    match = regex.search(prompt)
    return short(prompt[max(0, match.start() - 80) : match.end() + 160], 320) if match else ""


def feature_value(prompt: str, feature: str) -> tuple[str, str, str]:
    patterns = FEATURE_PATTERNS.get(feature, [])
    for value, pattern in patterns:
        evidence = first_evidence(prompt, pattern)
        if evidence:
            confidence = "high" if value not in {"implicit", "partial", "moderate"} else "medium"
            return value, evidence, confidence
    defaults = {
        "evidence_requirement": "none", "evidence_quote_required": "no", "explicit_scoring_anchors": "none",
        "negation_handling": "absent", "missing_information_rule": "unspecified", "temporal_constraint": "absent",
        "frequency_requirement": "absent", "inference_permission": "unspecified", "speaker_restriction": "absent",
        "abstention_permission": "no", "output_rigidity": "free_text", "itemwise_reasoning_requirement": "no",
        "uncertainty_requirement": "none",
    }
    return defaults.get(feature, "unspecified"), "", "high"


def build_feature_rows(variants: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant_id, variant in variants.items():
        for cid, prompt in sorted(variant["prompts"].items()):
            if cid > 16 or not prompt:
                continue
            for feature in FEATURE_PATTERNS:
                value, evidence, confidence = feature_value(prompt, feature)
                rows.append({
                    "dataset": variant["dataset"],
                    "prompt_source_variant": variant_id,
                    "condition": f"C{cid:02d}",
                    "prompt_template_id": prompt_id(prompt),
                    "feature": feature,
                    "feature_value": value,
                    "feature_evidence_quote": evidence,
                    "auto_confidence": confidence,
                    "review_required": "yes" if value in {"unspecified", "uncertain"} or confidence == "low" else "no",
                    "coding_basis": "prompt text/code output only; no model performance fields used",
                })
    return rows


def diff_lines(a: str, b: str) -> tuple[list[str], list[str], str]:
    a_lines = normalize_prompt(a).splitlines()
    b_lines = normalize_prompt(b).splitlines()
    diff = list(difflib.unified_diff(a_lines, b_lines, fromfile="baseline", tofile="target", lineterm=""))
    added = [x[1:] for x in diff if x.startswith("+") and not x.startswith("+++")]
    removed = [x[1:] for x in diff if x.startswith("-") and not x.startswith("---")]
    return added, removed, "\n".join(diff)


def descriptor_only(changes: list[str]) -> bool:
    if not changes:
        return False
    descriptor = re.compile(r"(?i)(输入文本|input text|临床访谈|临床记录|访谈片段|事件序列|clinical interview|clinical record|event sequence|fragment)")
    return all(descriptor.search(line) for line in changes)


def classify_pair(added: list[str], removed: list[str], exact_same: bool) -> tuple[str, str]:
    if exact_same:
        return "clean_single_factor", "single_factor_interpretation"
    changes = added + removed
    if descriptor_only(changes):
        return "mostly_single_factor", "single_factor_interpretation"
    if any(re.search(r"(?i)(score|评分|confidence|置信|evidence|证据|infer|推断|JSON|probabil|9\b|总分|severity|严重度)", x) for x in changes):
        return "multi_component_change", "bundle_interpretation_only"
    return "uncertain", "no_clean_interpretation"


def build_pair_rows(variants: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant_id, variant in variants.items():
        if variant["dataset"] not in {"HAMD-17", "PHQ-8"}:
            continue
        for baseline, target, factor, factor_zh in PAIR_DEFS:
            a = variant["prompts"].get(baseline, "")
            b = variant["prompts"].get(target, "")
            if not a or not b:
                status, interpretation = "not_comparable", "no_clean_interpretation"
                added, removed, udiff = [], [], ""
            else:
                added, removed, udiff = diff_lines(a, b)
                status, interpretation = classify_pair(added, removed, normalize_prompt(a) == normalize_prompt(b))
            rows.append({
                "dataset": variant["dataset"],
                "prompt_source_variant": variant_id,
                "pathway": "itemwise_score" if baseline == 3 else "direct_grade",
                "baseline_condition": f"C{baseline:02d}",
                "target_condition": f"C{target:02d}",
                "intended_manipulation": factor,
                "intended_manipulation_zh": factor_zh,
                "baseline_template_id": prompt_id(a) if a else "",
                "target_template_id": prompt_id(b) if b else "",
                "exact_same": "yes" if a == b and a else "no",
                "normalized_same": "yes" if normalize_prompt(a) == normalize_prompt(b) and a and b else "no",
                "changed_line_n": len(set(added + removed)),
                "added_line_n": len(added),
                "removed_line_n": len(removed),
                "added_text": "\n".join(added),
                "removed_text": "\n".join(removed),
                "unified_diff": udiff,
                "observed_changes": "prompt unchanged; manipulation is input-path only" if a and normalize_prompt(a) == normalize_prompt(b) else ("input descriptor wording only" if descriptor_only(added + removed) else "substantive prompt text change"),
                "unexpected_changes": "no" if status in {"clean_single_factor", "mostly_single_factor"} else "yes",
                "single_factor_status": status,
                "interpretation_allowed": interpretation,
                "notes": "descriptor wording is treated as input metadata, not a new psychological prompt mechanism" if status == "mostly_single_factor" else "",
            })
    return rows


def build_source_comparison(variants: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    pairs = [("HAMD_code", "HAMD_docx"), ("HAMD_code", "PHQ_docx"), ("HAMD_docx", "PHQ_docx")]
    rows: list[dict[str, Any]] = []
    for left_id, right_id in pairs:
        if left_id not in variants or right_id not in variants:
            continue
        left, right = variants[left_id], variants[right_id]
        for cid in range(1, 17):
            a, b = left["prompts"].get(cid, ""), right["prompts"].get(cid, "")
            added, removed, udiff = diff_lines(a, b) if a and b else ([], [], "")
            rows.append({
                "left_source_variant": left_id,
                "right_source_variant": right_id,
                "left_dataset": left["dataset"],
                "right_dataset": right["dataset"],
                "condition": f"C{cid:02d}",
                "left_template_id": prompt_id(a) if a else "",
                "right_template_id": prompt_id(b) if b else "",
                "exact_same": "yes" if a and a == b else "no",
                "normalized_same": "yes" if a and b and normalize_prompt(a) == normalize_prompt(b) else "no",
                "changed_line_n": len(set(added + removed)),
                "added_line_n": len(added),
                "removed_line_n": len(removed),
                "unified_diff": udiff,
                "notes": "HAMD/PHQ使用不同量表提示词是预期差异；该表不是条件效应比较。",
            })
    return rows


def build_frozen_rows(condition_rows: list[dict[str, Any]], feature_rows: list[dict[str, Any]], template_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    feature_map: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in feature_rows:
        feature_map.setdefault((row["dataset"], row["prompt_source_variant"], row["condition"]), {})[row["feature"]] = row["feature_value"]
    template_map = {(row["dataset"], row["prompt_source_variant"], row["condition"]): row for row in template_rows}
    rows: list[dict[str, Any]] = []
    for row in condition_rows:
        source_tokens = row["runtime_prompt_source"].split(";")
        variant_ids: list[str] = []
        for token in source_tokens:
            if row["dataset"] == "HAMD-17" and token == "code_builder":
                variant_ids.append("HAMD_code")
            elif row["dataset"] == "HAMD-17" and token == "docx_override":
                variant_ids.append("HAMD_docx")
            elif row["dataset"] == "PHQ-8" and token == "docx_override":
                variant_ids.append("PHQ_docx")
        for variant_id in variant_ids:
            key = (row["dataset"], variant_id, row["condition"])
            template = template_map.get(key)
            if not template:
                continue
            out = {
                "dataset": row["dataset"],
                "prompt_source_variant": variant_id,
                "condition": row["condition"],
                "condition_name": row["condition_name"],
                "pathway": row["pathway"],
                "cleaned": row["cleaned"],
                "structured": row["structured"],
                "text_scope": row["text_scope"],
                "baseline_condition": row["baseline_condition"],
                "intended_manipulation": row["intended_manipulation"],
                "intended_pair": row["intended_pair"],
                "prompt_template_id": template["prompt_template_id"],
                "normalized_sha256": template["normalized_sha256"],
                "static_character_count": template["character_count"],
                "static_line_count": template["line_count"],
                "estimated_token_count": template["estimated_token_count"],
                "input_code_key": row["input_code_key"],
                "input_type": row["input_type"],
                "input_path_expression": row["input_path_expression"],
                "thinking_mode_control": row["thinking_mode_control"],
            }
            out.update(feature_map.get(key, {}))
            rows.append(out)
    return rows


def make_source_rows(project_root: Path, repo_root: Path, scripts_dir: Path, source_paths: dict[str, Path], workbook_info: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, path in source_paths.items():
        row = {
            "source_label": label,
            "source_kind": "workbook" if path.suffix.lower() == ".xlsx" else "docx" if path.suffix.lower() == ".docx" else "code",
            "path": relative_path(path, project_root),
            "exists": "yes" if path.exists() else "no",
            "size_bytes": path.stat().st_size if path.exists() else "",
            "sha256": sha256_file(path) if path.exists() else "",
            "used_as_authority": "yes",
            "notes": "source workbook read-only; source code and prompt DOCX are the authority for this module",
        }
        rows.append(row)
    rows.append({
        "source_label": "source_workbook_integrity",
        "source_kind": "workbook_check",
        "path": relative_path(Path(workbook_info["path"]), repo_root),
        "exists": "yes",
        "size_bytes": workbook_info["size_bytes"],
        "sha256": workbook_info["sha256_before"],
        "used_as_authority": "provenance_only",
        "notes": f"actual_xlsx={workbook_info['is_actual_xlsx']}; unchanged={workbook_info.get('unchanged')}; scan={workbook_info.get('scan_status')}",
    })
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def build_manual_review(run_rows: list[dict[str, Any]], template_rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]], variants: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    version_sources: dict[str, set[str]] = defaultdict(set)
    version_manifest_paths: dict[str, list[str]] = defaultdict(list)
    for run in run_rows:
        key = f"{run['dataset']}|{run['prompt_version']}"
        version_sources[key].add(run["source_mode"])
        version_manifest_paths[key].append(run["manifest_path"])
    for key, sources in sorted(version_sources.items()):
        if len(sources) > 1:
            dataset, version = key.split("|", 1)
            rows.append({
                "review_id": f"version_source_ambiguity:{key}",
                "review_type": "same_prompt_version_multiple_source_modes",
                "dataset": dataset,
                "prompt_version": version,
                "source_evidence": ";".join(sorted(sources)),
                "manifest_examples": ";".join(version_manifest_paths[key][:5]),
                "reason": "同一prompt_version在运行manifest中同时出现code_builder和docx_override；需要确认该版本标签是否被复用。",
                "reviewer_code": "",
                "reviewer_note": "",
                "resolved": "",
            })
    for row in pair_rows:
        if row["single_factor_status"] in {"uncertain", "multi_component_change", "not_comparable"}:
            rows.append({
                "review_id": f"pair:{row['dataset']}:{row['prompt_source_variant']}:{row['baseline_condition']}>{row['target_condition']}",
                "review_type": "pairwise_prompt_interpretation",
                "dataset": row["dataset"],
                "prompt_source_variant": row["prompt_source_variant"],
                "condition": f"{row['baseline_condition']}->{row['target_condition']}",
                "source_evidence": short(row.get("unified_diff", ""), 1200),
                "reason": row["single_factor_status"],
                "reviewer_code": "",
                "reviewer_note": "",
                "resolved": "",
            })
    for variant_id, variant in variants.items():
        if variant["extraction_status"] not in {"extracted_from_docx", "code_builder_extracted"}:
            rows.append({
                "review_id": f"source_parse:{variant_id}",
                "review_type": "prompt_source_parse",
                "dataset": variant["dataset"],
                "prompt_source_variant": variant_id,
                "source_evidence": variant["source_file"],
                "reason": variant["extraction_status"],
                "reviewer_code": "",
                "reviewer_note": "",
                "resolved": "",
            })
    return rows


def write_report(output_dir: Path, workbook_info: dict[str, Any], conditions: list[dict[str, Any]], variants: dict[str, dict[str, Any]], trace_rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]], manual_rows: list[dict[str, Any]], run_rows: list[dict[str, Any]]) -> None:
    pair_summary = Counter(row["single_factor_status"] for row in pair_rows)
    lines = [
        "# PDCH C01-C16代码级提示词与实验条件追溯",
        "",
        "> 本模块只追溯代码、运行manifest和固定提示词来源；不使用模型结果，不进行性能关联分析。",
        "",
        "## 结论先行",
        "",
        f"- `9eval_main.py` 的 `CONDITIONS` 共解析到 {len(conditions)} 条，C01-C16全部纳入。",
        f"- C01-C16的输入路径由 `DATA_PATHS` 和 `clean`/`C` 字段决定；固定提示词由 `build_system_prompt → build_condition_prompt` 组装。",
        f"- `PDCH_PROMPT_DOCX` 存在时，`word_prompt_templates.py` 在导入时用 `prompt_docx_loader.load_prompt_docx` 覆盖条件提示词；因此“代码生成”和“DOCX覆盖”被分开追溯。",
        f"- 观察到的运行manifest为 {len(run_rows)} 个（含历史/探针记录），同一版本的来源模式冲突待复核 {sum(1 for r in manual_rows if r['review_type']=='same_prompt_version_multiple_source_modes')} 条。",
        f"- 六组理论pair的代码级提示词状态计数：{dict(pair_summary)}。即使提示词正文完全相同，清洗/规整/文本范围仍然可能通过输入路径发生操纵；不能把输入操纵误写成prompt文字操纵。",
        "",
        "## 如何读主表",
        "",
        "1. `01_condition_code_trace.csv`：先看每个条件的 `input_path_expression`、`input_code_key`、`prompt_builder_call` 和 `runtime_prompt_source`。",
        "2. `03_prompt_source_comparison.csv`：只比较HAMD/PHQ不同提示词来源的正文，不解释为条件效应。",
        "3. `04_pairwise_diff.csv`：六组pair的实际固定prompt diff；`mostly_single_factor`只表示输入描述文字变化，不把它当成新的心理机制。",
        "4. `06_remaining_manual_review.csv`：只保留代码无法消除的版本来源冲突或真实diff歧义；不再要求逐条审核原来的161条语义编码。",
        "",
        "## 研究边界",
        "",
        "- `thinking_mode`不是C01-C16条件字典字段；它由`PDCH_ENABLE_THINKING`和模型名回退逻辑控制，已在主表单独记录。",
        "- C03→C04、C01→C02等clean pair在固定prompt不变时，解释为输入清洗操纵；C03→C07、C01→C05等可能只改变输入类型描述，代码级上属于输入处理/descriptor变化。",
        "- 不根据MAE、准确率、置信度或任何预测字段定义prompt特征；冻结表不含gold、prediction、MAE、NAE、accuracy、bias、F1。",
        "",
        "## 输入工作簿完整性",
        "",
        f"- 文件：`{workbook_info['path']}`",
        f"- 大小：{workbook_info['size_bytes']} bytes；ZIP头：{workbook_info['is_actual_xlsx']}；SHA-256：`{workbook_info['sha256_before']}`",
        f"- 读取后SHA是否一致：`{workbook_info.get('unchanged')}`；扫描状态：`{workbook_info.get('scan_status')}`",
        "",
        "## 输出",
        "",
        "- `01_condition_code_trace.csv`",
        "- `02_prompt_version_provenance.csv`",
        "- `03_prompt_source_comparison.csv`",
        "- `04_pairwise_diff.csv`",
        "- `05_prompt_feature_coding.csv`",
        "- `06_remaining_manual_review.csv`",
        "- `07_frozen_input.csv`",
        "- `08_prompt_templates.csv`",
        "- `09_source_files.csv`",
        "- `10_run_contexts.csv`",
        "- `11_workbook_summary.json`",
        "- `12_code_trace_qa.json`",
        "- `PDCH_PHQ_HAMD_代码级条件追溯_20260810.xlsx`（由这些CSV生成的可读总表）",
    ]
    (output_dir / "13_code_trace_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    project_root = (args.project_root or repo_root.parent).resolve()
    scripts_dir = project_root / "_新结构_待启用" / "scripts"
    prepared_root = project_root / "_新结构_待启用" / "PHQ全量189人_调用就绪"
    output_dir = (args.output_dir or (repo_root / "prompt_design_audit_20260810" / "code_trace_20260810")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    workbook_path = repo_root / "PDCH_PHQ_HAMD_所有模型所有条件_提示词字段完整修正版_20260807.xlsx"
    hamd_docx = next((p for p in [project_root / "正式使用提示词.docx", project_root / "_新结构_待启用" / "hamd正式使用提示词.docx"] if p.exists()), project_root / "_新结构_待启用" / "hamd正式使用提示词.docx")
    phq_candidates = [prepared_root / "prompts" / "PHQ8_prompt_set_3_nonconditional_24_conditions_English.docx", project_root / "_新结构_待启用" / "PHQ数据" / "PHQ8_prompt_set_3_nonconditional_24_conditions_English.docx", project_root / "_新结构_待启用" / "PHQ行号数据" / "PHQ8_prompt_set_3_nonconditional_24_conditions_English.docx"]
    phq_docx = next((p for p in phq_candidates if p.exists()), phq_candidates[0])
    source_script_paths = {
        "9eval_main.py": scripts_dir / "9eval_main.py",
        "word_prompt_templates.py": scripts_dir / "word_prompt_templates.py",
        "prompt_docx_loader.py": scripts_dir / "prompt_docx_loader.py",
        "high_concurrency_repair.py": scripts_dir / "high_concurrency_repair.py",
        "runtime_config.py": scripts_dir / "runtime_config.py",
        "run_hamd_remaining_3models.py": scripts_dir / "run_hamd_remaining_3models.py",
        "run_PHQ全量189人.ps1": prepared_root / "run_PHQ全量189人.ps1",
        "hamd_prompt_docx": hamd_docx,
        "phq_prompt_docx": phq_docx,
        "source_workbook": workbook_path,
    }
    # Keep duplicate local prompt copies in the provenance table.  They are
    # not copied into the repository; their hashes show whether the runtime
    # path and the authoring path contain the same bytes.
    hamd_runtime_copy = project_root / "_新结构_待启用" / "hamd正式使用提示词.docx"
    phq_data_copy = project_root / "_新结构_待启用" / "PHQ数据" / "PHQ8_prompt_set_3_nonconditional_24_conditions_English.docx"
    phq_line_copy = project_root / "_新结构_待启用" / "PHQ行号数据" / "PHQ8_prompt_set_3_nonconditional_24_conditions_English.docx"
    if hamd_runtime_copy.exists():
        source_script_paths["hamd_prompt_docx_runtime_copy"] = hamd_runtime_copy
    if phq_data_copy.exists():
        source_script_paths["phq_prompt_docx_phq_data_copy"] = phq_data_copy
    if phq_line_copy.exists():
        source_script_paths["phq_prompt_docx_line_number_copy"] = phq_line_copy
    required = [scripts_dir / "9eval_main.py", scripts_dir / "word_prompt_templates.py", scripts_dir / "high_concurrency_repair.py", workbook_path]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit("Required source missing: " + "; ".join(missing))

    workbook_info = scan_workbook(workbook_path)
    conditions, _ = parse_conditions(scripts_dir / "9eval_main.py")
    data_paths, _ = parse_data_paths(scripts_dir / "9eval_main.py")
    builder = load_code_builder(scripts_dir)
    code_prompts = {int(cond["id"]): builder.build_condition_prompt(cond) for cond in conditions}
    hamd_loaded = parse_docx(hamd_docx, "zh")
    phq_loaded = parse_docx(phq_docx, "en")
    variants = {
        "HAMD_code": {"dataset": "HAMD-17", "source_kind": "code_builder", "source_file": relative_path(scripts_dir / "word_prompt_templates.py", project_root), "source_file_sha256": sha256_file(scripts_dir / "word_prompt_templates.py"), "extraction_status": "code_builder_extracted", "prompts": code_prompts},
        "HAMD_docx": {"dataset": "HAMD-17", "source_kind": "docx_override", "source_file": relative_path(hamd_docx, project_root), "source_file_sha256": hamd_loaded.get("docx_sha256", ""), "extraction_status": hamd_loaded.get("status", ""), "prompts": hamd_loaded.get("conditions", {})},
        "PHQ_docx": {"dataset": "PHQ-8", "source_kind": "docx_override", "source_file": relative_path(phq_docx, project_root), "source_file_sha256": phq_loaded.get("docx_sha256", ""), "extraction_status": phq_loaded.get("status", ""), "prompts": phq_loaded.get("conditions", {})},
    }
    run_rows = scan_run_manifests(project_root)
    trace_rows = build_condition_rows(conditions, data_paths, source_script_paths, run_rows, project_root, scripts_dir)
    template_rows = build_template_rows(variants, project_root)
    feature_rows = build_feature_rows(variants)
    pair_rows = build_pair_rows(variants)
    comparison_rows = build_source_comparison(variants)
    frozen_rows = build_frozen_rows(trace_rows, feature_rows, template_rows)
    source_rows = make_source_rows(project_root, repo_root, scripts_dir, source_script_paths, workbook_info)
    manual_rows = build_manual_review(run_rows, template_rows, pair_rows, variants)

    csv_map = {
        "01_condition_code_trace.csv": trace_rows,
        "02_prompt_version_provenance.csv": run_rows,
        "03_prompt_source_comparison.csv": comparison_rows,
        "04_pairwise_diff.csv": pair_rows,
        "05_prompt_feature_coding.csv": feature_rows,
        "06_remaining_manual_review.csv": manual_rows,
        "07_frozen_input.csv": frozen_rows,
        "08_prompt_templates.csv": template_rows,
        "09_source_files.csv": source_rows,
        "10_run_contexts.csv": run_rows,
    }
    for filename, rows in csv_map.items():
        write_csv(output_dir / filename, rows)
    (output_dir / "11_workbook_summary.json").write_text(json.dumps(workbook_info, ensure_ascii=False, indent=2), encoding="utf-8")

    result_fields = {"gold", "prediction", "predicted_score", "mae", "nae", "accuracy", "sensitivity", "specificity", "bias", "f1", "correct", "true_score", "model_score"}
    frozen_fields = set(frozen_rows[0]) if frozen_rows else set()
    version_mode_counts: dict[str, set[str]] = defaultdict(set)
    for row in run_rows:
        version_mode_counts[f"{row['dataset']}|{row['prompt_version']}"].add(row["source_mode"])
    qa = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS_WITH_REVIEW" if manual_rows else "PASS",
        "source_workbook": {"path": str(workbook_path), "size_bytes": workbook_info["size_bytes"], "actual_xlsx": workbook_info["is_actual_xlsx"], "sha256_before": workbook_info["sha256_before"], "sha256_after": workbook_info.get("sha256_after"), "unchanged": workbook_info.get("unchanged")},
        "conditions_total": len(conditions),
        "c01_c16_complete": sorted(int(c["id"]) for c in conditions[:16]) == list(range(1, 17)),
        "data_path_keys": sorted(data_paths),
        "variants": {key: {"dataset": value["dataset"], "source_file": value["source_file"], "source_file_sha256": value["source_file_sha256"], "condition_n": len(value["prompts"]), "extraction_status": value["extraction_status"]} for key, value in variants.items()},
        "run_manifest_n": len(run_rows),
        "version_source_ambiguity_n": sum(1 for sources in version_mode_counts.values() if len(sources) > 1),
        "pair_rows": len(pair_rows),
        "pair_status_counts": dict(Counter(row["single_factor_status"] for row in pair_rows)),
        "manual_review_n": len(manual_rows),
        "frozen_input_rows": len(frozen_rows),
        "frozen_input_forbidden_fields": sorted(frozen_fields & result_fields),
        "source_files_missing": [row["source_label"] for row in source_rows if row["exists"] != "yes"],
        "no_api_key_written": True,
        "no_result_association_performed": True,
    }
    (output_dir / "12_code_trace_qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(output_dir, workbook_info, conditions, variants, trace_rows, pair_rows, manual_rows, run_rows)
    print(json.dumps({"output_dir": str(output_dir), "trace_rows": len(trace_rows), "template_rows": len(template_rows), "feature_rows": len(feature_rows), "pair_rows": len(pair_rows), "manual_review_n": len(manual_rows), "qa_status": qa["status"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
