import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = path.resolve(process.argv[2] || "prompt_design_audit_20260810/code_trace_20260810");
const output = path.join(outputDir, "PDCH_PHQ_HAMD_代码级条件追溯_20260810.xlsx");

function parseCsv(input) {
  const text = input.replace(/^\uFEFF/, "");
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"') {
        if (text[i + 1] === '"') { field += '"'; i += 1; } else quoted = false;
      } else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') { row.push(field); field = ""; }
    else if (ch === '\n') { row.push(field.endsWith('\r') ? field.slice(0, -1) : field); if (!(row.length === 1 && row[0] === "")) rows.push(row); row = []; field = ""; }
    else field += ch;
  }
  if (field.length || row.length) { row.push(field.endsWith('\r') ? field.slice(0, -1) : field); rows.push(row); }
  return rows;
}

function colName(n) {
  let x = n; let out = "";
  while (x > 0) { const r = (x - 1) % 26; out = String.fromCharCode(65 + r) + out; x = Math.floor((x - 1) / 26); }
  return out;
}

function writeMatrix(sheet, inputRows, options = {}) {
  const rows = inputRows.length ? inputRows : [["（空）"]];
  const width = Math.max(...rows.map((r) => r.length));
  const matrix = rows.map((r) => Array.from({ length: width }, (_, i) => r[i] ?? ""));
  for (let start = 0; start < matrix.length; start += 500) {
    const part = matrix.slice(start, Math.min(matrix.length, start + 500));
    sheet.getRangeByIndexes(start, 0, part.length, width).values = part;
  }
  const used = sheet.getRangeByIndexes(0, 0, matrix.length, width);
  if (!options.compact) {
    used.format.wrapText = true;
    used.format.verticalAlignment = "top";
    used.format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
  }
  const header = sheet.getRangeByIndexes(0, 0, 1, width);
  header.format.fill = "#1F4E78";
  header.format.font = { bold: true, color: "#FFFFFF" };
  header.format.horizontalAlignment = "center";
  header.format.rowHeight = 30;
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
  for (let c = 0; c < width; c += 1) {
    const h = String(matrix[0][c] ?? "").toLowerCase();
    const wide = /prompt|diff|evidence|quote|reason|note|text|source|hash|instruction|rubric|path|expression|manifest|template/.test(h);
    sheet.getRangeByIndexes(0, c, Math.min(matrix.length, 100), 1).format.columnWidth = wide ? 46 : 18;
  }
  if (options.highlightColumn !== undefined && matrix.length > 1) {
    sheet.getRangeByIndexes(1, options.highlightColumn, matrix.length - 1, 1).format.fill = options.highlightFill || "#FFF2CC";
  }
}

function jsonRows(obj) {
  return [["字段", "值"], ...Object.entries(obj).map(([key, value]) => [key, typeof value === "object" ? JSON.stringify(value) : value])];
}

async function loadCsv(filename) { return parseCsv(await fs.readFile(path.join(outputDir, filename), "utf8")); }

async function main() {
  const qa = JSON.parse(await fs.readFile(path.join(outputDir, "12_code_trace_qa.json"), "utf8"));
  const summary = JSON.parse(await fs.readFile(path.join(outputDir, "11_workbook_summary.json"), "utf8"));
  const workbook = Workbook.create();

  const coreRows = [
    ["结论", "代码级条件追溯结果"],
    ["本页回答", "条件 → 输入路径 → 提示词来源 → 版本 → 评分路径；并核对六组pair是否真实单因素。"],
    ["核心结论1", `CONDITIONS共${qa.conditions_total}条；C01-C16完整解析=${qa.c01_c16_complete ? "是" : "否"}。`],
    ["核心结论2", "条件先改变输入路径/输入类型；提示词由9eval_main.py → word_prompt_templates.py组装。设置PDCH_PROMPT_DOCX时，DOCX正文覆盖代码默认正文。"],
    ["核心结论3", `六组pair状态：${JSON.stringify(qa.pair_status_counts)}。C03→C04、C01→C02固定prompt不变，是输入清洗；C03→C07、C01→C05只有输入descriptor文字差异。`],
    ["核心结论4", `同一版本的运行来源模式冲突${qa.version_source_ambiguity_n}组，因此目前只保留${qa.manual_review_n}条剩余复核；不再要求人工审核原来的161条语义编码。`],
    ["思考模式", "不是C01-C16条件字段；由PDCH_ENABLE_THINKING覆盖，未设置时GLM/MiniMax按代码回退为true，其余按false。"],
    ["数据边界", "本模块不读取gold/prediction/MAE/accuracy等结果变量做任何关联；冻结输入也不含这些字段。"],
    ["源工作簿", summary.path],
    ["源文件大小", summary.size_bytes],
    ["源文件SHA-256", summary.sha256_before],
    ["源文件是否修改", qa.source_workbook.unchanged ? "否" : "是（失败）"],
    ["先看哪几页", "02_条件代码追溯 → 03_提示词版本来源 → 05_六组Pair差分 → 07_剩余人工复核 → 08_冻结分析输入"],
    ["如何解释", "先区分输入操纵与固定提示词操纵；只有05_六组Pair差分中的真实prompt差异才可讨论提示词文字变化。"],
  ];
  const core = workbook.worksheets.add("01_核心结论");
  writeMatrix(core, coreRows);
  core.getRange("A:A").format.columnWidth = 24;
  core.getRange("B:B").format.columnWidth = 80;
  core.getRange("B2:B14").format.wrapText = true;
  core.getRange("B2:B14").format.rowHeight = 42;
  core.getRange("A2:A14").format.font = { bold: true };
  core.getRange("A1:B1").format.fill = "#17365D";
  core.getRange("A1:B1").format.font = { bold: true, color: "#FFFFFF" };

  const specs = [
    ["02_条件代码追溯", "01_condition_code_trace.csv", { highlightColumn: 24, highlightFill: "#E2F0D9" }],
    ["03_提示词版本来源", "02_prompt_version_provenance.csv"],
    ["04_提示词来源比较", "03_prompt_source_comparison.csv"],
    ["05_六组Pair差分", "04_pairwise_diff.csv", { highlightColumn: 19, highlightFill: "#E2F0D9" }],
    ["06_提示词特征编码", "05_prompt_feature_coding.csv", { compact: true }],
    ["07_剩余人工复核", "06_remaining_manual_review.csv", { highlightColumn: 0, highlightFill: "#FFF2CC" }],
    ["08_冻结分析输入", "07_frozen_input.csv"],
    ["09_提示词模板正文", "08_prompt_templates.csv", { compact: true }],
    ["10_源文件盘点", "09_source_files.csv", { compact: true }],
    ["11_运行上下文", "10_run_contexts.csv", { compact: true }],
  ];
  for (const [sheetName, filename, options] of specs) {
    const sheet = workbook.worksheets.add(sheetName);
    writeMatrix(sheet, await loadCsv(filename), options || {});
  }
  const qaSheet = workbook.worksheets.add("12_QA");
  writeMatrix(qaSheet, jsonRows(qa));
  const summarySheet = workbook.worksheets.add("13_工作簿摘要");
  writeMatrix(summarySheet, jsonRows(summary));

  const inspect = await workbook.inspect({ kind: "workbook,sheet", maxChars: 12000, tableMaxRows: 3, tableMaxCols: 8 });
  await fs.writeFile(path.join(outputDir, "workbook_inspect.json"), inspect.ndjson ?? String(inspect), "utf8");
  const formulas = await workbook.inspect({ kind: "formula", maxChars: 3000, options: { maxResults: 50 } });
  await fs.writeFile(path.join(outputDir, "workbook_formula_inspect.json"), formulas.ndjson ?? String(formulas), "utf8");
  if (process.env.DO_RENDER === "1") {
    const previewDir = path.join(outputDir, "_qa_previews");
    await fs.mkdir(previewDir, { recursive: true });
    const preview = await workbook.render({ sheetName: "01_核心结论", range: "A1:B14", autoCrop: "all", scale: 1, format: "png" });
    await fs.writeFile(path.join(previewDir, "01_核心结论.png"), new Uint8Array(await preview.arrayBuffer()));
  }
  await fs.mkdir(outputDir, { recursive: true });
  const blob = await SpreadsheetFile.exportXlsx(workbook);
  await blob.save(output);
  console.log(JSON.stringify({ output, sheets: workbook.worksheets.items.length, inspect: "workbook_inspect.json", formula_inspect: "workbook_formula_inspect.json" }, null, 2));
}

await main();
