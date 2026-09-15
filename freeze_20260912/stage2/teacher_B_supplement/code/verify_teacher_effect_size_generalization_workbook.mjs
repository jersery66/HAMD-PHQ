import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "../..");
const outputArg = process.argv.indexOf("--output-dir");
const outputDir = path.resolve(root, outputArg >= 0 ? process.argv[outputArg + 1] : "outputs/pdch_teacher_effect_size_selection_generalization_20260915");
const workbookArg = process.argv.indexOf("--workbook");
const workbookName = workbookArg >= 0 ? process.argv[workbookArg + 1] : (outputDir.includes("teacher_B_supplement") ? "老师要求_B方案外推结果.xlsx" : "老师要求_A方案外推结果.xlsx");
const workbookPath = path.join(outputDir, workbookName);
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));

const expectedSheets = ["00_结论", "01_方案选择", "02_外推主结果", "03_折分分布", "04_条目条件映射", "05_方法与核验"];
const observedSheets = workbook.worksheets.items.map((sheet) => sheet.name);
const summary = await workbook.inspect({ kind: "region", sheetId: "00_结论", range: "A1:D25", maxChars: 12000 });
const formulas = await workbook.inspect({ kind: "formula", sheetId: "02_外推主结果", range: "W1:Z12", maxChars: 8000 });
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "saved workbook formula error scan" });
const drawings = await workbook.inspect({ kind: "drawing", sheetId: "00_结论", maxChars: 5000 });

const summaryText = summary.ndjson;
const formulaText = formulas.ndjson;
const drawingText = drawings.ndjson;
const strategy = outputDir.includes("teacher_B_supplement") ? "B" : "A";
const checks = [
  { check: "six_expected_sheets", pass: JSON.stringify(observedSheets) === JSON.stringify(expectedSheets), observed: observedSheets },
  { check: "summary_contains_requested_strategy", pass: summaryText.includes("最终方案") && summaryText.includes(strategy), observed: `summary contains ${strategy}` },
  { check: "summary_contains_PHQ_and_HAMD_decisions", pass: summaryText.includes("2/3 AI 支持") && summaryText.includes("0/3 AI 支持"), observed: "PHQ 2/3; HAMD 0/3" },
  { check: "primary_sheet_keeps_formula_columns", pass: formulaText.includes("(F5-E5)/F5") && formulaText.includes("AND(G5<0,I5<0,K5<0.05)"), observed: formulaText },
  { check: "saved_workbook_has_no_formula_errors", pass: errors.ndjson.includes("matched 0 entries"), observed: errors.ndjson },
  { check: "summary_has_embedded_forest_figure", pass: drawingText.includes('"drawingType":"image"'), observed: drawingText },
];
const report = {
  status: checks.every((row) => row.pass) ? "PASS" : "FAIL",
  workbook: path.basename(workbookPath),
  checks: checks.map((row) => ({ check: row.check, status: row.pass ? "PASS" : "FAIL", observed: row.observed })),
  failures: checks.filter((row) => !row.pass).map((row) => row.check),
};
await fs.writeFile(path.join(outputDir, "saved_workbook_verification.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8");
await fs.writeFile(path.join(outputDir, "saved_workbook_summary_inspect.ndjson"), summary.ndjson, "utf8");
await fs.writeFile(path.join(outputDir, "saved_workbook_formula_inspect.ndjson"), formulas.ndjson, "utf8");
console.log(JSON.stringify({ status: report.status, checks: checks.length, failures: report.failures }));
if (report.status !== "PASS") process.exit(1);
