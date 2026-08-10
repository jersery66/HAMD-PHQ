import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(process.argv[2] || "prompt_design_audit_20260810");
const output = path.join(root, "PDCH_PHQ_HAMD_提示词设计与操纵审计总表_20260807.xlsx");

const csvFiles = [
  ["02_原始字段盘点", "01_prompt_field_inventory.csv"],
  ["03_唯一提示词模板", "02_unique_prompt_templates.csv"],
  ["04_条件设计字典", "03_condition_design_dictionary.csv"],
  ["05_提示词差分", "04_prompt_pairwise_diff.csv"],
  ["06_提示词特征", "05_prompt_feature_coding.csv"],
  ["07_人工复核", "06_prompt_feature_manual_review.csv"],
  ["08_操纵真实性", "07_prompt_manipulation_audit.csv"],
  ["09_冻结分析输入", "08_prompt_analysis_frozen_input.csv"],
  ["10_数据质量问题", "10_data_quality_issues.csv"],
  ["11_编码规则", "11_coding_rules.csv"],
  ["12_结果索引", "12_result_index.csv"],
];

function parseCsv(input) {
  const s = input.replace(/^\uFEFF/, "");
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < s.length; i += 1) {
    const ch = s[i];
    if (quoted) {
      if (ch === '"') {
        if (s[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          quoted = false;
        }
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\n") {
      row.push(field.endsWith("\r") ? field.slice(0, -1) : field);
      field = "";
      if (!(row.length === 1 && row[0] === "")) rows.push(row);
      row = [];
    } else {
      field += ch;
    }
  }
  if (field.length || row.length) {
    row.push(field.endsWith("\r") ? field.slice(0, -1) : field);
    rows.push(row);
  }
  return rows;
}

function colName(n) {
  let x = n;
  let out = "";
  while (x > 0) {
    const r = (x - 1) % 26;
    out = String.fromCharCode(65 + r) + out;
    x = Math.floor((x - 1) / 26);
  }
  return out;
}

function coreRows(meta, csvCounts) {
  return [
    ["项目", "说明"],
    ["目的", "审计固定提示词设计与C01-C16操纵真实性；冻结提示词变量，暂不与模型性能结果关联。"],
    ["源结果工作簿", meta.input_path],
    ["源文件大小（bytes）", meta.input_size],
    ["源文件SHA-256", meta.input_sha256],
    ["源文件是否被修改", meta.input_unchanged ? "否（前后SHA一致）" : "是（失败）"],
    ["固定提示词来源", "HAMD-17：本地hamd正式使用提示词.docx；PHQ-8：本地PHQ8_prompt_set_3_nonconditional_24_conditions_English.docx"],
    ["条件来源", "9eval_main.py的CONDITIONS字面量（AST读取），不是人工根据旧聊天记录填写。"],
    ["静态/动态边界", "template hash只包含固定system prompt；被试ID、访谈文本、事件、路径、模型输出和金标准均不进入hash。"],
    ["标准化规则", "CRLF→LF、删除行尾空格、删除首尾无意义空白、压缩连续空行；不改写语义。"],
    ["观察到的上下文数", meta.contexts],
    ["唯一固定模板数", meta.unique_prompt_templates],
    ["C01-C16稳定性怎么读", "先看05_提示词差分的exact/normalized_same、版本列和single_factor_status；版本不同或缺失时不能宣称实际请求相同。"],
    ["六组pair", "C03→C04、C03→C07、C03→C11、C01→C02、C01→C05、C01→C09。"],
    ["人工复核", "07_人工复核中的reviewer_code、reviewer_note、resolved保持空白，等待人工确认。"],
    ["冻结分析输入", "09_冻结分析输入只含设计变量、提示词特征和非性能覆盖元数据；禁止出现gold/prediction/MAE/NAE/accuracy/bias/F1等结果字段。"],
    ["停止规则", "本任务完成提示词审计后停止；不自动进行prompt feature→模型结果的关联分析。"],
    ["CSV行数", JSON.stringify(csvCounts)],
  ];
}

function writeMatrix(sheet, rows) {
  if (!rows.length) return;
  const width = Math.max(...rows.map((r) => r.length));
  const matrix = rows.map((r) => Array.from({ length: width }, (_, i) => r[i] ?? ""));
  const block = 500;
  for (let start = 0; start < matrix.length; start += block) {
    const part = matrix.slice(start, Math.min(matrix.length, start + block));
    const endRow = start + part.length;
    const range = sheet.getRangeByIndexes(start, 0, part.length, width);
    range.values = part;
  }
  const used = sheet.getRangeByIndexes(0, 0, matrix.length, width);
  used.format.wrapText = true;
  used.format.verticalAlignment = "top";
  used.format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
  const header = sheet.getRangeByIndexes(0, 0, 1, width);
  header.format.fill = "#1F4E78";
  header.format.font = { bold: true, color: "#FFFFFF" };
  header.format.horizontalAlignment = "center";
  header.format.rowHeight = 32;
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
  for (let c = 0; c < width; c += 1) {
    const h = String(matrix[0][c] ?? "").toLowerCase();
    const wide = /prompt|diff|evidence|quote|reason|note|text|source|hash|instruction|rubric|output/.test(h);
    const widthValue = wide ? 44 : 18;
    sheet.getRange(`${colName(c + 1)}:${colName(c + 1)}`).format.columnWidth = widthValue;
  }
}

async function main() {
  const meta = JSON.parse(await fs.readFile(path.join(root, "audit_metadata.json"), "utf8"));
  const csvCounts = meta.csv_rows;
  const workbook = Workbook.create();
  const core = workbook.worksheets.add("01_核心说明");
  writeMatrix(core, coreRows(meta, csvCounts));
  core.getRange("A:A").format.columnWidth = 28;
  core.getRange("B:B").format.columnWidth = 100;
  core.getRange("A2:A18").format.font = { bold: true, color: "#1F1F1F" };
  // Artifact-tool's renderer is optional here because it can hang on this
  // Windows desktop runtime even for a compact sheet.  Set DO_RENDER=1 to
  // retry it; structural inspection and openpyxl verification remain the
  // release gates.
  if (process.env.DO_RENDER === "1") {
    const previewDir = path.join(root, "_qa_previews");
    await fs.mkdir(previewDir, { recursive: true });
    const preview = await workbook.render({ sheetName: "01_核心说明", range: "A1:B18", autoCrop: "all", scale: 1, format: "png" });
    const previewBytes = new Uint8Array(await preview.arrayBuffer());
    await fs.writeFile(path.join(previewDir, "01_核心说明.png"), previewBytes);
  }

  for (const [sheetName, filename] of csvFiles) {
    const csv = await fs.readFile(path.join(root, filename), "utf8");
    const rows = parseCsv(csv);
    const sheet = workbook.worksheets.add(sheetName);
    writeMatrix(sheet, rows);
    if (sheetName === "07_人工复核") {
      if (rows.length > 1) sheet.getRangeByIndexes(1, 0, rows.length - 1, 1).format.fill = "#FFF2CC";
    }
    if (sheetName === "08_操纵真实性") {
      if (rows.length > 1) sheet.getRangeByIndexes(1, 12, rows.length - 1, 2).format.fill = "#E2F0D9";
    }
    if (sheetName === "10_数据质量问题") {
      if (rows.length > 1) sheet.getRangeByIndexes(1, 0, rows.length - 1, 1).format.fill = "#FCE4D6";
    }
  }

  const inspectSummary = await workbook.inspect({
    kind: "workbook,sheet",
    maxChars: 10000,
    tableMaxRows: 3,
    tableMaxCols: 8,
  });
  await fs.writeFile(path.join(root, "workbook_inspect.json"), inspectSummary.ndjson ?? String(inspectSummary), "utf8");
  const formulaInspect = await workbook.inspect({ kind: "formula", maxChars: 3000, options: { maxResults: 50 } });
  await fs.writeFile(path.join(root, "workbook_formula_inspect.json"), formulaInspect.ndjson ?? String(formulaInspect), "utf8");

  await fs.mkdir(path.dirname(output), { recursive: true });
  const blob = await SpreadsheetFile.exportXlsx(workbook);
  await blob.save(output);
  // The long-text sheets are intentionally not rendered; they were inspected
  // structurally and the compact core sheet was rendered above.
  console.log(JSON.stringify({ output, sheets: workbook.worksheets.items.length, inspect: "workbook_inspect.json", formula_inspect: "workbook_formula_inspect.json" }, null, 2));
}

await main();
