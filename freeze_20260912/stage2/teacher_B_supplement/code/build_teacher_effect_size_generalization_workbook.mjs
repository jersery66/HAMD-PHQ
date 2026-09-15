import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const DEFAULT_OUTPUT = "outputs/pdch_teacher_effect_size_selection_generalization_20260915";
const FONT = "Arial";
const NAVY = "#17365D";
const TEAL = "#0F6B78";
const BLUE = "#2F75B5";
const LIGHT_BLUE = "#DDEBF7";
const PALE_GREEN = "#E2F0D9";
const PALE_YELLOW = "#FFF2CC";
const PALE_RED = "#FCE4D6";
const GREY = "#F2F2F2";

function colLetter(index) {
  let n = index + 1;
  let out = "";
  while (n > 0) {
    const r = (n - 1) % 26;
    out = String.fromCharCode(65 + r) + out;
    n = Math.floor((n - 1) / 26);
  }
  return out;
}

function normalize(value) {
  if (value === undefined || value === null) return null;
  if (typeof value === "number" && !Number.isFinite(value)) return null;
  if (Array.isArray(value) || (typeof value === "object" && value !== null)) return JSON.stringify(value);
  return value;
}

function values(rows, columns) {
  return rows.map((row) => columns.map((column) => normalize(row[column.key])));
}

function styleTitle(sheet, title, note, lastColumnIndex) {
  const last = colLetter(Math.max(lastColumnIndex, 1));
  sheet.mergeCells(`A1:${last}1`);
  sheet.getRange("A1").values = [[title]];
  sheet.getRange("A1").format = {
    fill: NAVY,
    font: { bold: true, color: "#FFFFFF", size: 15, name: FONT },
    horizontalAlignment: "left",
    verticalAlignment: "center",
  };
  sheet.getRange("A1").format.rowHeightPx = 34;
  sheet.mergeCells(`A2:${last}2`);
  sheet.getRange("A2").values = [[note]];
  sheet.getRange("A2").format = {
    fill: LIGHT_BLUE,
    font: { color: "#404040", size: 9, name: FONT },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange("A2").format.rowHeightPx = 46;
  sheet.showGridLines = false;
}

function styleSection(sheet, cell, text, width = 4) {
  const match = /^([A-Z]+)(\d+)$/.exec(cell);
  const column = match[1];
  const row = Number(match[2]);
  const start = column.charCodeAt(0) - 65;
  const end = colLetter(start + width - 1);
  sheet.mergeCells(`${cell}:${end}${row}`);
  sheet.getRange(cell).values = [[text]];
  sheet.getRange(cell).format = {
    fill: GREY,
    font: { bold: true, color: NAVY, size: 10, name: FONT },
    verticalAlignment: "center",
  };
}

function setColumnWidths(sheet, columns) {
  columns.forEach((column, index) => {
    const width = column.width ?? (
      /说明|依据|边界|结论|下一步|状态|reason|distribution/i.test(column.label) ? 230
        : /模型|条目|条件|量表|strategy/i.test(column.label) ? 125
          : /CI|MAE|NAE|rho|kappa|效应|比例|频率|熵|p|q/i.test(column.label) ? 92
            : 82
    );
    sheet.getRangeByIndexes(0, index, 1, 1).format.columnWidthPx = width;
  });
}

function addTable(sheet, startRowZero, columns, rows, tableName, options = {}) {
  const startCol = options.startCol ?? 0;
  const header = sheet.getRangeByIndexes(startRowZero, startCol, 1, columns.length);
  header.values = [columns.map((column) => column.label)];
  header.format = {
    fill: options.headerFill ?? TEAL,
    font: { bold: true, color: "#FFFFFF", size: 9, name: FONT },
    wrapText: true,
    horizontalAlignment: "center",
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: "#B4C6E7" },
  };
  header.format.rowHeightPx = 36;
  const matrix = values(rows, columns);
  if (matrix.length) {
    const data = sheet.getRangeByIndexes(startRowZero + 1, startCol, matrix.length, columns.length);
    data.values = matrix;
    data.format = {
      font: { size: 9, name: FONT },
      verticalAlignment: "center",
      borders: { preset: "insideHorizontal", style: "thin", color: "#E7E6E6" },
    };
    const last = colLetter(startCol + columns.length - 1);
    const first = colLetter(startCol);
    const table = sheet.tables.add(`${first}${startRowZero + 1}:${last}${startRowZero + matrix.length + 1}`, true, tableName);
    table.style = "TableStyleMedium2";
    columns.forEach((column, index) => {
      if (column.format) {
        sheet.getRangeByIndexes(startRowZero + 1, startCol + index, matrix.length, 1).format.numberFormat = column.format;
      }
      if (column.wrap) {
        sheet.getRangeByIndexes(startRowZero + 1, startCol + index, matrix.length, 1).format.wrapText = true;
      }
    });
  }
  setColumnWidths(sheet, columns);
  return { firstDataRow: startRowZero + 2, lastDataRow: startRowZero + matrix.length + 1, rowCount: matrix.length };
}

function addMethodRows(sheet, startRowZero, rows, tableName) {
  return addTable(
    sheet,
    startRowZero,
    [
      { key: "topic", label: "步骤/问题", width: 180 },
      { key: "why", label: "为什么这样做", width: 620, wrap: true },
    ],
    rows,
    tableName,
  );
}

async function main() {
  const outputArg = process.argv.indexOf("--output-dir");
  const requested = outputArg >= 0 ? process.argv[outputArg + 1] : DEFAULT_OUTPUT;
  const rootArg = process.argv.indexOf("--project-root");
  const projectRoot = rootArg >= 0 ? path.resolve(process.argv[rootArg + 1]) : path.resolve(import.meta.dirname, "../..");
  const outputDir = path.resolve(projectRoot, requested);
  const payload = JSON.parse(await fs.readFile(path.join(outputDir, "workbook_payload.json"), "utf8"));
  const manifest = JSON.parse(await fs.readFile(path.join(outputDir, "run_manifest.json"), "utf8"));
  const independent = JSON.parse(await fs.readFile(path.join(outputDir, "independent_verification_report.json"), "utf8"));
  const strategy = payload.selected_strategy;
  if (!["A", "B"].includes(strategy)) throw new Error(`Workbook input has unsupported strategy ${strategy}`);
  if (manifest.verification_status !== "PASS" || independent.status !== "PASS") throw new Error("Verification gate is not PASS");

  const workbook = Workbook.create();
  const selection = [...payload.selection_summary].sort((a, b) => a.PHQ_effect_rank - b.PHQ_effect_rank);
  const selectedSummary = selection.find((row) => row.selected) ?? selection[0];
  const strategyDisplay = strategy === "A" ? "A" : "A（主） / B（补充）";
  const effectText = strategy === "A"
    ? `PHQ：A ${selectedSummary.PHQ_mean_delta_MAE.toFixed(3)}（g_z=${selectedSummary.PHQ_effect_gz.toFixed(3)}）；HAMD：A ${selectedSummary.HAMD_mean_delta_MAE.toFixed(3)}（g_z=${selectedSummary.HAMD_effect_gz.toFixed(3)}）`
    : `PHQ：A ${selectedSummary.PHQ_mean_delta_MAE.toFixed(3)} / B ${selection.find((row) => row.strategy === "B").PHQ_mean_delta_MAE.toFixed(3)}；HAMD：A ${selectedSummary.HAMD_mean_delta_MAE.toFixed(3)} / B ${selection.find((row) => row.strategy === "B").HAMD_mean_delta_MAE.toFixed(3)}`;
  const primary = [...payload.primary_inference].sort((a, b) => `${a.scale}|${a.model}`.localeCompare(`${b.scale}|${b.model}`));
  const decisionLookup = new Map(payload.decision_table.map((row) => [`${row.scale}|${row.model}`, row]));
  const combinedPrimary = primary.map((row) => ({
    ...row,
    ...decisionLookup.get(`${row.scale}|${row.model}`),
    label: `${row.scale.replace("-8", "").replace("-17", "")} / ${row.model}`,
    ci_text: `[${row.delta_total_MAE_CI_low.toFixed(3)}, ${row.delta_total_MAE_CI_high.toFixed(3)}]`,
    evidence_text: `q=${row.sign_flip_q.toFixed(4)}；改善折=${(row.fold_improvement_rate * 100).toFixed(0)}%`,
  }));

  let sheet = workbook.worksheets.add("00_结论");
  styleTitle(sheet, "老师要求的方案选择与重复五折外推结果", `先在 PHQ 和 HAMD 内部分别按总分 MAE 效应比较 A/B/C，再对本页的 ${strategy} 方案做每个 AI 独立的 10 次重复 × 5 折外推检验。负的 ΔMAE 表示优于 C03。`, 3);
  const kpis = [
    ["最终方案", strategyDisplay + (strategy === "B" ? "｜本页为补充外推" : "｜PHQ、HAMD 分别排名第 1")],
    ["方案选择效应", effectText],
    ["PHQ-8 外推", "2/3 AI 支持｜DeepSeek 与 Qwen 显著改善；GLM 无改善"],
    ["HAMD 外推", "0/3 AI 支持｜三个 AI 的置信区间均跨 0，暂不替换 C03"],
  ];
  kpis.forEach((row, index) => {
    const excelRow = 4 + index;
    sheet.getRange(`A${excelRow}`).values = [[row[0]]];
    sheet.mergeCells(`B${excelRow}:D${excelRow}`);
    sheet.getRange(`B${excelRow}`).values = [[row[1]]];
  });
  sheet.getRange("A4:D7").format = { font: { size: 10, name: FONT }, borders: { preset: "all", style: "thin", color: "#B4C6E7" }, verticalAlignment: "center", wrapText: true };
  sheet.getRange("A4:A7").format = { fill: NAVY, font: { bold: true, color: "#FFFFFF", size: 10, name: FONT } };
  sheet.getRange("B4:D7").format = { fill: PALE_YELLOW, font: { bold: true, color: NAVY, size: 10, name: FONT }, horizontalAlignment: "left" };

  styleSection(sheet, "A9", "结果怎样解释", 3);
  addTable(sheet, 9, [
    { key: "label", label: "量表 / AI", width: 165 },
    { key: "delta_total_MAE", label: "Δ总分MAE", format: "0.000", width: 68 },
    { key: "ci_text", label: "ΔMAE 95%CI", width: 112 },
    { key: "evidence_text", label: "FDR q / 50折改善率", width: 135 },
  ], combinedPrimary, "HeadlineResults");
  sheet.getRange("B11:B16").conditionalFormats.add("cellIs", { operator: "lessThan", formula: 0, format: { fill: PALE_GREEN } });
  styleSection(sheet, "A18", "每个 AI 接下来怎么处理", 4);
  sheet.getRange("A19").values = [["量表 / AI"]];
  sheet.mergeCells("B19:D19");
  sheet.getRange("B19").values = [["可以说什么"]];
  sheet.getRange("A19:D19").format = { fill: TEAL, font: { bold: true, color: "#FFFFFF", size: 9, name: FONT }, horizontalAlignment: "center", verticalAlignment: "center", borders: { preset: "all", style: "thin", color: "#B4C6E7" } };
  combinedPrimary.forEach((row, index) => {
    const excelRow = 20 + index;
    sheet.getRange(`A${excelRow}`).values = [[row.label]];
    sheet.mergeCells(`B${excelRow}:D${excelRow}`);
    sheet.getRange(`B${excelRow}`).values = [[row.claim_boundary]];
  });
  sheet.getRange("A20:D25").format = { font: { size: 9, name: FONT }, wrapText: true, verticalAlignment: "center", borders: { preset: "insideHorizontal", style: "thin", color: "#E7E6E6" } };
  sheet.getRange("B20:D25").conditionalFormats.add("containsText", { text: "不支持", format: { fill: PALE_RED } });
  sheet.getRange("B20:D25").conditionalFormats.add("containsText", { text: "仅支持总分", format: { fill: PALE_YELLOW } });
  const forestBytes = await fs.readFile(path.join(outputDir, "figures", `F2_${strategy}_generalization_forest.png`));
  sheet.images.add({
    dataUrl: `data:image/png;base64,${forestBytes.toString("base64")}`,
    anchor: { from: { row: 27, col: 0 }, extent: { widthPx: 520, heightPx: 235 } },
  });
  sheet.getRange("A55:D56").merge();
  sheet.getRange("A55").values = [[`图中负值表示 ${strategy} 的总分 MAE 更低；显著性和 95%CI 以顶部结果表为准。`]];
  sheet.getRange("A55").format = { fill: LIGHT_BLUE, font: { size: 9, name: FONT }, wrapText: true };
  sheet.freezePanes.freezeRows(3);

  sheet = workbook.worksheets.add("01_方案选择");
  styleTitle(sheet, "A/B/C 方案选择：PHQ 与 HAMD 分开排名", "PHQ 和 HAMD 是不同量表，分别按本量表的整体总分 MAE 改善排名；同一量表内的 AI-equal Hedges g_z 作为森林图辅助表达。越负表示总分 MAE 改善越大。", 18);
  const selectionColumns = [
    { key: "strategy", label: "方案" },
    { key: "PHQ_mean_delta_MAE", label: "PHQ平均ΔMAE", format: "0.000" },
    { key: "PHQ_effect_gz", label: "PHQ AI-equal g_z", format: "0.000" },
    { key: "PHQ_effect_rank", label: "PHQ排名", format: "0" },
    { key: "HAMD_mean_delta_MAE", label: "HAMD平均ΔMAE", format: "0.000" },
    { key: "HAMD_effect_gz", label: "HAMD AI-equal g_z", format: "0.000" },
    { key: "HAMD_effect_rank", label: "HAMD排名", format: "0" },
    { key: "level1_cells", label: "Level1单元", format: "0" },
    { key: "level2_cells", label: "Level2单元", format: "0" },
    { key: "selected", label: "进入后续" },
  ];
  addTable(sheet, 3, selectionColumns, selection, "StrategySelection");
  sheet.getRange("B5:B7").conditionalFormats.add("colorScale", { colors: ["#63BE7B", "#FFEB84", "#F8696B"], thresholds: ["min", "50%", "max"] });
  styleSection(sheet, "A9", "条目真实性、稳定性和复制证据", 4);
  addTable(sheet, 9, [
    { key: "strategy", label: "方案" },
    { key: "coverage_noninferiority_cells", label: "coverage非劣单元", format: "0" },
    { key: "stability_acceptable_cells", label: "稳定性通过单元", format: "0" },
    { key: "test47_replication_support_cells", label: "test47支持单元", format: "0" },
    { key: "mean_delta_item_NAE", label: "平均Δ条目NAE", format: "0.0000" },
    { key: "mean_delta_cancellation_ratio", label: "平均Δ抵消率", format: "0.0000" },
    { key: "selected", label: "进入后续" },
    { key: "selection_reason", label: "选择解释", width: 420, wrap: true },
  ], selection, "StrategySecondaryEvidence");
  styleSection(sheet, "A15", "选择规则与解释边界", 3);
  addMethodRows(sheet, 15, [
    { topic: "主要选择标准", why: "老师后续要求比较验证折总分 MAE，所以前一步也按总分 MAE 的跨量表标准化合并效应选方案，保证选择结局与验证结局一致。" },
    { topic: "为什么不是 B", why: "B 的条目真实性证据更均衡，且出现唯一 Level2/test47 支持；但在 PHQ 和 HAMD 分开看的整体总分 MAE 效应量中都低于 A。按本次会议规则，B 不进入后续主检验。" },
    { topic: `${strategy} 的风险`, why: `${strategy} 在既有探索中可能伴随条目 NAE、条目绝对误差或误差抵消增加。因此即便总分显著改善，也只能支持总分优化，不能写成逐条评分更准。` },
    { topic: "为什么不把六个 AI 单元直接合并", why: "同一受试者在多个 AI 下重复出现，六个效应并不独立；PHQ 和 HAMD 也不是同一测量尺度。这里按量表分开排名，AI-equal composite 只在各自量表内做描述。" },
  ], "SelectionRationale");
  sheet.freezePanes.freezeRows(4);

  sheet = workbook.worksheets.add("02_外推主结果");
  styleTitle(sheet, `${strategy} 方案：每个 AI 独立的重复五折外推结果`, "PHQ 全 189 人；HAMD 全 99 人、主分析排除 H14，使用 HAMD16-core。正式推断单位为受试者；50 个重叠折仅描述稳定性。", 25);
  const primaryColumns = [
    { key: "scale", label: "量表", width: 90 },
    { key: "analysis_layer", label: "分析层", width: 115 },
    { key: "model", label: "AI", width: 145 },
    { key: "paired_subject_n", label: "配对N", format: "0" },
    { key: "selected_total_MAE", label: `${strategy}总分MAE`, format: "0.000" },
    { key: "C03_total_MAE", label: "C03总分MAE", format: "0.000" },
    { key: "delta_total_MAE", label: "Δ总分MAE", format: "0.000" },
    { key: "delta_total_MAE_CI_low", label: "95%CI下限", format: "0.000" },
    { key: "delta_total_MAE_CI_high", label: "95%CI上限", format: "0.000" },
    { key: "sign_flip_p", label: "sign-flip p", format: "0.0000" },
    { key: "sign_flip_q", label: "FDR q", format: "0.0000" },
    { key: "paired_t_p", label: "配对t p", format: "0.0000" },
    { key: "wilcoxon_p", label: "Wilcoxon p", format: "0.0000" },
    { key: "hedges_gz", label: "Hedges g_z", format: "0.000" },
    { key: "fold_improvement_rate", label: "50折改善率", format: "0.0%" },
    { key: "delta_item_NAE", label: "Δ条目NAE", format: "0.0000" },
    { key: "delta_sum_item_AE", label: "Δ条目绝对误差和", format: "0.000" },
    { key: "delta_cancellation_ratio", label: "Δ抵消率", format: "0.0000" },
    { key: "selected_weighted_kappa", label: `${strategy} weighted kappa`, format: "0.000" },
    { key: "C03_weighted_kappa", label: "C03 weighted kappa", format: "0.000" },
    { key: "C03_retention_rate", label: `${strategy}中C03保留率`, format: "0.0%" },
    { key: "median_item_route_top_frequency", label: "条目路由中位最高频率", format: "0.0%" },
  ];
  const block = addTable(sheet, 3, primaryColumns, primary, "PrimaryInference");
  const formulaStart = primaryColumns.length;
  const formulaHeaders = ["相对改善率（公式）", "总分外推判定（公式）", "结论边界", "建议处理"];
  sheet.getRangeByIndexes(3, formulaStart, 1, formulaHeaders.length).values = [formulaHeaders];
  sheet.getRangeByIndexes(3, formulaStart, 1, formulaHeaders.length).format = { fill: NAVY, font: { bold: true, color: "#FFFFFF", size: 9, name: FONT }, wrapText: true, horizontalAlignment: "center" };
  sheet.getRange("W1").format.columnWidthPx = 100;
  sheet.getRange("X1").format.columnWidthPx = 135;
  sheet.getRange("Y1").format.columnWidthPx = 285;
  sheet.getRange("Z1").format.columnWidthPx = 310;
  const rowByKey = new Map(payload.decision_table.map((row) => [`${row.scale}|${row.model}`, row]));
  primary.forEach((row, index) => {
    const excelRow = block.firstDataRow + index;
    sheet.getRange(`W${excelRow}`).formulas = [[`=IF(F${excelRow}=0,"",(F${excelRow}-E${excelRow})/F${excelRow})`]];
    sheet.getRange(`X${excelRow}`).formulas = [[`=IF(AND(G${excelRow}<0,I${excelRow}<0,K${excelRow}<0.05),"支持","不支持")`]];
    const decision = rowByKey.get(`${row.scale}|${row.model}`);
    sheet.getRange(`Y${excelRow}:Z${excelRow}`).values = [[decision.claim_boundary, decision.recommended_next_action]];
  });
  sheet.getRange(`W${block.firstDataRow}:W${block.lastDataRow}`).format.numberFormat = "0.0%";
  sheet.getRange(`Y${block.firstDataRow}:Z${block.lastDataRow}`).format.wrapText = true;
  sheet.getRange(`G${block.firstDataRow}:G${block.lastDataRow}`).conditionalFormats.add("cellIs", { operator: "lessThan", formula: 0, format: { fill: PALE_GREEN } });
  sheet.getRange(`X${block.firstDataRow}:X${block.lastDataRow}`).conditionalFormats.add("containsText", { text: "支持", format: { fill: PALE_GREEN } });
  sheet.getRange(`X${block.firstDataRow}:X${block.lastDataRow}`).conditionalFormats.add("containsText", { text: "不支持", format: { fill: PALE_RED } });
  sheet.freezePanes.freezeRows(4);
  sheet.freezePanes.freezeColumns(3);

  sheet = workbook.worksheets.add("03_折分分布");
  styleTitle(sheet, `10 次重复 × 5 折的 ${strategy} held-out 效应分布`, "每行是一折的描述性结果，共 6 个量表×AI 单元 × 50 折。由于重复折共享受试者，这 50 个值不作为独立样本做正式 t 检验。", 11);
  const foldRows = [...payload.fold_distribution].sort((a, b) => `${a.scale}|${a.model}|${a.repeat}|${a.fold}`.localeCompare(`${b.scale}|${b.model}|${b.repeat}|${b.fold}`));
  const foldColumns = [
    { key: "scale", label: "量表", width: 90 },
    { key: "analysis_layer", label: "分析层", width: 115 },
    { key: "model", label: "AI", width: 145 },
    { key: "repeat", label: "重复", format: "0" },
    { key: "fold", label: "折", format: "0" },
    { key: "heldout_subject_n", label: "验证折N", format: "0" },
    { key: "selected_MAE", label: `${strategy} MAE`, format: "0.000" },
    { key: "C03_MAE", label: "C03 MAE", format: "0.000" },
    { key: "delta_MAE", label: "ΔMAE", format: "0.000" },
    { key: "delta_item_NAE", label: "Δ条目NAE", format: "0.0000" },
    { key: "delta_cancellation_ratio", label: "Δ抵消率", format: "0.0000" },
    { key: "improved", label: "该折改善" },
  ];
  const foldBlock = addTable(sheet, 3, foldColumns, foldRows, "FoldEffects");
  sheet.getRange(`I${foldBlock.firstDataRow}:I${foldBlock.lastDataRow}`).conditionalFormats.add("cellIs", { operator: "lessThan", formula: 0, format: { fill: PALE_GREEN } });
  sheet.getRange(`L${foldBlock.firstDataRow}:L${foldBlock.lastDataRow}`).conditionalFormats.add("cellIs", { operator: "equal", formula: "TRUE", format: { fill: PALE_GREEN } });
  sheet.freezePanes.freezeRows(4);
  sheet.freezePanes.freezeColumns(3);

  sheet = workbook.worksheets.add("04_条目条件映射");
  styleTitle(sheet, `全队列 ${strategy} 条件映射与外层路由稳定性`, "全队列映射用于未来新增受试者的固定候选规则，不参与当前 OOF 效应估计。未通过外推检验的模型明确标记为保留 C03。HAMD H14 不进入主分析。", 23);
  const mapRows = [...payload.full_cohort_candidate_maps].sort((a, b) => `${a.scale}|${a.model}|${String(a.item_id).padStart(2, "0")}`.localeCompare(`${b.scale}|${b.model}|${String(b.item_id).padStart(2, "0")}`));
  const mapColumns = [
    { key: "scale", label: "量表", width: 90 },
    { key: "analysis_layer", label: "分析层", width: 115 },
    { key: "model", label: "AI", width: 145 },
    { key: "item_id", label: "条目", format: "0" },
    { key: "item_name", label: "条目名称", width: 190 },
    { key: "full_cohort_selected_condition", label: `全队列${strategy}条件`, width: 105 },
    { key: "selection_reason", label: "选择原因", width: 200, wrap: true },
    { key: "full_cohort_common_subject_n", label: "共同训练N", format: "0" },
    { key: "selected_corrected_rho", label: "选中校正rho", format: "0.000" },
    { key: "selected_item_MAE", label: "选中条目MAE", format: "0.000" },
    { key: "C03_item_MAE", label: "C03条目MAE", format: "0.000" },
    { key: "delta_item_MAE", label: "Δ条目MAE", format: "0.000" },
    { key: "selected_coverage", label: "选中coverage", format: "0.0%" },
    { key: "C03_coverage", label: "C03 coverage", format: "0.0%" },
    { key: "outer_route_top_condition", label: "50折众数条件", width: 105 },
    { key: "outer_route_top_frequency", label: "众数频率", format: "0.0%" },
    { key: "outer_route_normalized_entropy", label: "归一化熵", format: "0.000" },
    { key: "full_map_matches_outer_mode", label: "全样本=折众数" },
    { key: "cell_total_generalization_supported", label: "所在AI总分外推支持" },
    { key: "future_use_status", label: "未来使用状态", width: 350, wrap: true },
  ];
  const mapBlock = addTable(sheet, 3, mapColumns, mapRows, "FullCohortMaps");
  sheet.getRange(`T${mapBlock.firstDataRow}:T${mapBlock.lastDataRow}`).conditionalFormats.add("containsText", { text: "不建议", format: { fill: PALE_RED } });
  sheet.getRange(`T${mapBlock.firstDataRow}:T${mapBlock.lastDataRow}`).conditionalFormats.add("containsText", { text: "前瞻候选", format: { fill: PALE_YELLOW } });
  sheet.freezePanes.freezeRows(4);
  sheet.freezePanes.freezeColumns(5);

  sheet = workbook.worksheets.add("05_方法与核验");
  styleTitle(sheet, "为什么这样做，以及结果如何核验", "本页记录分析决策、适用边界、固定输入哈希和两层验证。主运行检查与独立重算均通过才允许交付。", 5);
  addMethodRows(sheet, 3, [
    { topic: "为什么 PHQ 用 189 人", why: "老师明确要求不再固定 dev/test，而是在全 189 人中做重复五折，让每个人都在每次重复中恰好作为一次 held-out 验证对象。" },
    { topic: "为什么 HAMD 用 99 人", why: "这是具有 PDCH HAMD 金标准的完整队列。H14 的金标准 9 表示不可评估，因此主结果使用其余 16 个可评估条目。" },
    { topic: "为什么 10 次重复五折", why: "单次五折可能受随机划分影响。复用冻结的 10×5 折可以观察 50 个 held-out 效应的分布，同时正式检验仍回到受试者层面。" },
    { topic: "为什么每个 AI 单独做", why: "老师要判断同一方案在不同 AI 上的外推性；既有 Cross-AI 路由更差，已作为补充分支封存，不再混入主路径。" },
    { topic: "为什么用配对检验", why: `${strategy} 与 C03 在同一 held-out 受试者上产生误差，配对比较能直接估计每个人的误差变化。10 次 OOF 先在受试者内平均，避免把重复结果当成独立样本。` },
    { topic: "为什么 sign-flip + bootstrap", why: "sign-flip 不依赖差值正态性，bootstrap 给出受试者层面的 95%CI；paired t 与 Wilcoxon 只作敏感性核对。" },
    { topic: "为什么做 FDR", why: "每个量表同时检验三个 AI，BH-FDR 控制同一问题族内的多重比较。" },
    { topic: "能写到什么程度", why: `可写 PHQ/DeepSeek 与 PHQ/Qwen 在当前队列内具有${strategy}总分 MAE 的跨受试者内部泛化证据；HAMD 和 PHQ/GLM 不支持。所有 ${strategy} 结果的条目误差或抵消均未同步改善。` },
    { topic: "仍缺什么", why: "策略选择与重复五折仍使用重叠队列，因此不是独立外部验证。下一步应锁定映射，在新样本或新中心前瞻测试；在此之前不能写临床部署或普遍泛化。" },
  ], "MethodsWhy");
  styleSection(sheet, "A15", "固定输入与运行信息", 2);
  addTable(sheet, 15, [
    { key: "field", label: "字段", width: 230 },
    { key: "value", label: "值", width: 620, wrap: true },
  ], [
    { field: "分析方案", value: manifest.analysis_name },
    { field: "选择规则", value: manifest.selection_rule },
    { field: "PHQ 折分 SHA-256", value: manifest.folds.PHQ_sha256 },
    { field: "HAMD 折分 SHA-256", value: manifest.folds.HAMD_sha256 },
    { field: "源数据 SHA-256", value: manifest.source_sha256 },
    { field: "折分设计", value: manifest.folds.design },
    { field: "正式推断", value: manifest.inference },
    { field: "原始数据改动", value: String(manifest.raw_data_modified) },
    { field: "LLM 调用", value: String(manifest.llm_calls) },
  ], "RunManifest");
  styleSection(sheet, "A28", "主运行检查", 3);
  const mainCheckRows = payload.checks.map((row) => ({ check: row.check, status: row.status, observed: String(row.observed) }));
  addTable(sheet, 28, [
    { key: "check", label: "检查项", width: 330 },
    { key: "status", label: "状态", width: 90 },
    { key: "observed", label: "观测", width: 280, wrap: true },
  ], mainCheckRows, "MainChecks");
  const independentStart = 30 + mainCheckRows.length + 2;
  styleSection(sheet, `A${independentStart}`, "独立重算检查", 3);
  const independentRows = independent.checks.map((row) => ({ check: row.check, status: row.status, observed: normalize(row.observed) }));
  addTable(sheet, independentStart, [
    { key: "check", label: "检查项", width: 330 },
    { key: "status", label: "状态", width: 90 },
    { key: "observed", label: "观测", width: 520, wrap: true },
  ], independentRows, "IndependentChecks");
  sheet.freezePanes.freezeRows(3);

  workbook.recalculate();
  const inspect = await workbook.inspect({ kind: "workbook,sheet,table,drawing", maxChars: 18000, tableMaxRows: 5, tableMaxCols: 12 });
  await fs.writeFile(path.join(outputDir, "workbook_inspect.ndjson"), inspect.ndjson, "utf8");
  const formulaErrors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "formula error scan" });
  await fs.writeFile(path.join(outputDir, "workbook_formula_error_scan.ndjson"), formulaErrors.ndjson, "utf8");
  const drawingInspect = await workbook.inspect({ kind: "drawing", sheetId: "00_结论", maxChars: 5000 });
  await fs.writeFile(path.join(outputDir, "workbook_drawing_inspect.ndjson"), drawingInspect.ndjson, "utf8");

  const sheetNames = ["00_结论", "01_方案选择", "02_外推主结果", "03_折分分布", "04_条目条件映射", "05_方法与核验"];
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  const outputName = `老师要求_${strategy}方案外推结果.xlsx`;
  const outputPath = path.join(outputDir, outputName);
  await xlsx.save(outputPath);
  await fs.writeFile(path.join(outputDir, "workbook_build_audit.json"), `${JSON.stringify({ status: "PASS", output: outputName, strategy, sheets: sheetNames, chartCount: 0, imageCount: 1, sourceVerification: manifest.verification_status, independentVerification: independent.status, visualVerification: "pending external per-sheet render because Artifact Tool render timed out before first preview" }, null, 2)}\n`, "utf8");
  console.log(JSON.stringify({ status: "PASS", output: outputPath, sheets: sheetNames.length, chartCount: 0, imageCount: 1 }, null, 2));
}

await main();
