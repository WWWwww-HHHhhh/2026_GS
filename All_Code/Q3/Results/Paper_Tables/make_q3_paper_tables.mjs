import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "file:///C:/Users/34957/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const outputDir = path.dirname(fileURLToPath(import.meta.url));
const workbook = Workbook.create();
const font = "Microsoft YaHei";
const headerFill = "#AE CDE6".replace(" ", "");
const subheaderFill = "#E5F1FA";
const accentFill = "#FFF2CC";

const planRows = [
  ["2025-03-20", 0, 632.84, 0, 705.18, 708.30, 0, 73765.55, 45123.05],
  ["2025-06-21", 0, 0, 0, 269.29, 381.56, 0, 39524.69, 23354.81],
  ["2025-09-23", 0, 469.53, 0, 698.03, 813.72, 47.05, 78594.08, 49839.75],
  ["2025-12-21", 0, 1064.01, 0, 871.09, 719.97, 0, 100632.36, 64502.74],
];

const adjustedRows = [
  ["2025-03-20", 0, 545.67, 0, 542.58, 708.30, 0, 68266.79, 43274.88],
  ["2025-06-21", 0, 0, 0, 254.50, 381.56, 0, 39498.99, 23344.05],
  ["2025-09-23", 0, 401.01, 0, 588.42, 813.72, 38.99, 73811.89, 48181.63],
  ["2025-12-21", 0, 975.90, 0, 871.09, 719.97, 0, 98783.27, 63859.54],
];

const purchaseHeader = [
  "日期", "10:00-10:10", "12:00-12:10", "14:00-14:10",
  "16:00-16:10", "18:00-18:10", "20:00-20:10",
  "全天购电量/kWh", "全天购电费/元",
];

function styleSheet(sheet, rangeAddress, headerAddress, numberAddress) {
  sheet.showGridLines = false;
  const used = sheet.getRange(rangeAddress);
  used.format.font = { name: font, size: 10 };
  used.format.verticalAlignment = "center";
  used.format.borders = { preset: "all", style: "thin", color: "#A6A6A6" };
  sheet.getRange(headerAddress).format = {
    fill: headerFill,
    font: { name: font, size: 10, bold: true, color: "#1F1F1F" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#7F7F7F" },
  };
  if (numberAddress) sheet.getRange(numberAddress).format.numberFormat = "0.00";
}

for (const [sheetName, title, rows] of [
  ["表1_计划购电", "表1  指定日期计划购电结果", planRows],
  ["补充表_调整购电", "补充表  指定日期最终调整购电结果", adjustedRows],
]) {
  const sheet = workbook.worksheets.add(sheetName);
  sheet.getRange("A1:I1").merge();
  sheet.getRange("A1").values = [[title]];
  sheet.getRange("A1:I1").format = {
    font: { name: font, size: 13, bold: true },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  sheet.getRange("A2:I6").values = [purchaseHeader, ...rows];
  styleSheet(sheet, "A2:I6", "A2:I2", "B3:I6");
  sheet.getRange("A3:A6").format.horizontalAlignment = "center";
  sheet.getRange("B3:I6").format.horizontalAlignment = "right";
  sheet.getRange("H3:I6").format.fill = subheaderFill;
  sheet.getRange("A8:I8").merge();
  sheet.getRange("A8").values = [[sheetName.startsWith("表1")
    ? "说明：购电量为每日0:00制定的计划值，数据取自result3.xlsx的“计划购电量”工作表。"
    : "说明：调整购电量为日内预报更新后最终生效的购电量，数据取自result3.xlsx的“调整购电量”工作表。"]];
  sheet.getRange("A8:I8").format = { font: { name: font, size: 9, italic: true, color: "#595959" }, wrapText: true };
  sheet.getRange("A1:I8").format.autofitColumns();
  sheet.getRange("A1:I8").format.autofitRows();
  sheet.getRange("A:A").format.columnWidth = 14;
  sheet.getRange("B:G").format.columnWidth = 13;
  sheet.getRange("H:I").format.columnWidth = 16;
  sheet.freezePanes.freezeRows(2);
}

const storage = workbook.worksheets.add("表2_储能");
storage.getRange("A1:E1").merge();
storage.getRange("A1").values = [["表2  指定日期储能充放电量"]];
storage.getRange("A2:E10").values = [
  ["时段", "2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"],
  ["0:00-4:00", "5258.74 / 0.00", "651.95 / 0.00", "9000.00 / 0.00", "9000.00 / 0.00"],
  ["4:00-8:00", "835.59 / 6283.64", "833.33 / 2069.66", "1666.67 / 5771.14", "2480.93 / 1492.89"],
  ["8:00-12:00", "5633.35 / 2358.19", "4685.74 / 0.00", "5833.33 / 2868.86", "5833.33 / 7740.49"],
  ["12:00-16:00", "5610.49 / 467.51", "6066.78 / 92.63", "5370.24 / 434.89", "8063.01 / 2691.52"],
  ["16:00-20:00", "6.40 / 5690.31", "49.07 / 5802.01", "0.00 / 5863.65", "35.99 / 5683.74"],
  ["20:00-24:00", "4590.44 / 2967.71", "1069.86 / 2854.65", "125.72 / 2878.19", "31.64 / 3001.73"],
  ["0:00储电量", 5317.13, 2162.87, 1200.00, 1200.00],
  ["24:00储电量", 5317.13, 2162.87, 1200.00, 1200.00],
];
storage.getRange("A1:E1").format = { font: { name: font, size: 13, bold: true }, horizontalAlignment: "center" };
styleSheet(storage, "A2:E10", "A2:E2", "B9:E10");
storage.getRange("A2:E10").format.horizontalAlignment = "center";
storage.getRange("A9:E10").format.fill = subheaderFill;
storage.getRange("A12:E12").merge();
storage.getRange("A12").values = [["说明：第3至第8行每格依次表示充电量和放电量，全部电量单位均为kWh。"]];
storage.getRange("A12:E12").format = { font: { name: font, size: 9, italic: true, color: "#595959" }, wrapText: true };
storage.getRange("A1:E12").format.autofitRows();
storage.getRange("A:A").format.columnWidth = 16;
storage.getRange("B:E").format.columnWidth = 20;
storage.freezePanes.freezeRows(2);

const emergencyData = {
  "2025-03-20": [
    ["0:20-0:30",22.976],["1:00-1:30",66.731],["3:10-4:00",52.938],["4:50-5:20",20.892],
    ["8:00-10:10",434.677],["10:50-12:00",209.763],["12:30-13:20",178.978],["13:50-14:10",25.030],
    ["14:50-15:00",0.720],["15:30-15:40",4.947],["15:50-16:10",35.978],["18:40-19:10",53.947],
    ["20:00-20:20",39.914],["21:20-21:40",7.899],["23:30-23:40",17.374]
  ],
  "2025-06-21": [["1:20-1:30",37.900],["3:10-3:30",37.000],["3:50-4:00",14.630],["6:50-7:00",25.576]],
  "2025-09-23": [["0:30-0:40",7.512],["5:40-5:50",3.722],["13:50-14:00",0.350],["14:20-14:30",1.999],["16:00-16:10",1.014],["20:10-20:30",13.100],["20:50-21:00",10.798],["22:20-22:30",5.675]],
  "2025-12-21": [["1:10-1:20",2.901],["3:30-3:50",58.291],["6:20-6:30",16.078],["9:40-9:50",37.685],["10:30-11:30",335.935],["12:50-13:00",4.183],["17:20-17:30",23.991],["18:10-19:00",95.399],["19:20-19:30",4.315],["19:40-20:00",47.769],["21:50-22:00",7.527]],
};
const totals = {"2025-03-20":1172.766,"2025-06-21":115.106,"2025-09-23":44.171,"2025-12-21":634.077};
const dates = Object.keys(emergencyData);
const emergency = workbook.worksheets.add("表3_紧急购电");
emergency.getRange("A1:H1").merge();
emergency.getRange("A1").values = [["表3  指定日期紧急购电结果"]];
const top = [];
for (const d of dates) top.push(d, "");
const sub = [];
for (let i=0;i<dates.length;i++) sub.push("时间段", "购电量/kWh");
const rows = [top, sub];
const maxLen = Math.max(...dates.map(d => emergencyData[d].length));
for (let i=0;i<maxLen;i++) {
  const row=[];
  for (const d of dates) {
    const item=emergencyData[d][i];
    row.push(item ? item[0] : "", item ? item[1] : null);
  }
  rows.push(row);
}
const totalRow=[];
for (const d of dates) totalRow.push("合计", totals[d]);
rows.push(totalRow);
emergency.getRange(`A2:H${rows.length+1}`).values = rows;
for (let c=0;c<8;c+=2) emergency.getRangeByIndexes(1,c,1,2).merge();
emergency.getRange("A1:H1").format = { font: { name: font, size: 13, bold: true }, horizontalAlignment: "center" };
styleSheet(emergency, `A2:H${rows.length+1}`, "A2:H3", `B4:B${rows.length+1}`);
for (const col of ["B","D","F","H"]) emergency.getRange(`${col}4:${col}${rows.length+1}`).format.numberFormat = "0.000";
emergency.getRange(`A2:H${rows.length+1}`).format.horizontalAlignment = "center";
emergency.getRange(`A${rows.length+1}:H${rows.length+1}`).format.fill = accentFill;
emergency.getRange(`A${rows.length+1}:H${rows.length+1}`).format.font = { name: font, size: 10, bold: true };
emergency.getRange("A:A").format.columnWidth = 14;
emergency.getRange("C:C").format.columnWidth = 14;
emergency.getRange("E:E").format.columnWidth = 14;
emergency.getRange("G:G").format.columnWidth = 14;
emergency.getRange("B:B").format.columnWidth = 13;
emergency.getRange("D:D").format.columnWidth = 13;
emergency.getRange("F:F").format.columnWidth = 13;
emergency.getRange("H:H").format.columnWidth = 13;
emergency.freezePanes.freezeRows(3);

const notes = workbook.worksheets.add("使用说明");
notes.getRange("A1:B7").values = [
  ["文件用途", "问题三正文表格的数据底稿"],
  ["表1_计划购电", "题目表1要求，列出4个指定日期的0:00计划购电结果"],
  ["补充表_调整购电", "问题三特有结果，列出日内预报更新后最终生效的调整购电结果"],
  ["表2_储能", "题目表2要求，单元格按“充电量 / 放电量”排列"],
  ["表3_紧急购电", "题目表3要求，相邻十分钟紧急购电时段已合并"],
  ["数值精度", "购电和储能结果保留2位小数，紧急购电结果保留3位小数"],
  ["数据来源", "Q3/Results/Tables/result3.xlsx"],
];
notes.showGridLines = false;
notes.getRange("A1:B7").format.font = { name: font, size: 10 };
notes.getRange("A1:A7").format.fill = subheaderFill;
notes.getRange("A1:A7").format.font = { name: font, size: 10, bold: true };
notes.getRange("A1:B7").format.borders = { preset: "all", style: "thin", color: "#BFBFBF" };
notes.getRange("A1:B7").format.verticalAlignment = "center";
notes.getRange("A1:B7").format.wrapText = true;
notes.getRange("A:A").format.columnWidth = 22;
notes.getRange("B:B").format.columnWidth = 62;
notes.getRange("A1:B7").format.autofitRows();

await fs.mkdir(outputDir, { recursive: true });
const out = await SpreadsheetFile.exportXlsx(workbook);
await out.save(path.join(outputDir, "q3_paper_tables.xlsx"));

const preview = await workbook.render({ sheetName: "表3_紧急购电", autoCrop: "all", scale: 1, format: "png" });
await fs.writeFile(path.join(process.env.TEMP, "q3_table3_preview.png"), new Uint8Array(await preview.arrayBuffer()));
