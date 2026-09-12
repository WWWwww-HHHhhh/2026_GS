import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const base = new URL("./results/", import.meta.url);
const repoRoot = process.env.CUMCM_REPO_ROOT ?? String.raw`D:\MathModel\2026_GS`;
const source = `${repoRoot}\\Data\\附件\\附件5\\result3.xlsx`;
const payload = JSON.parse(await fs.readFile(new URL("result3_payload.json", base), "utf8"));
if (payload.report_days !== 334 || payload.plan.length !== 334 || payload.adjusted.length !== 334
    || payload.charge.length !== 2004 || payload.emergency.length === 0) {
  throw new Error("Incomplete or invalid result3 payload");
}
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const plan = wb.worksheets.getItem("计划购电量");
const adjusted = wb.worksheets.getItem("调整购电量");
const storage = wb.worksheets.getItem("充放电量");
const emergency = wb.worksheets.getItem("紧急购电量");

for (const [sheet, rows] of [[plan,payload.plan],[adjusted,payload.adjusted]]) {
  sheet.getRangeByIndexes(1,1,334,146).values=rows.map(row=>row.slice(1));
  sheet.getRange("B2:EQ335").setNumberFormat("0.000000");
  sheet.getRange("EP2:EQ335").setNumberFormat("#,##0.00");
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(1);
}

// Repeat the official six-row storage form, then replace every value with the
// computed daily aggregates. No future row is used during optimization.
for (let day=4;day<334;day++) {
  storage.getRangeByIndexes(day*6+1,0,6,6).copyFrom(storage.getRange("A2:F7"),"all");
}
const storageRows=payload.charge.map(row=>row.map((value,col)=>
  col===0 && value!==null ? new Date(`${value}T00:00:00Z`) : value));
storage.getRangeByIndexes(1,0,storageRows.length,6).values=storageRows;
storage.getRangeByIndexes(1,0,storageRows.length,1).setNumberFormat("yyyy-mm-dd");
storage.getRangeByIndexes(1,2,storageRows.length,2).setNumberFormat("#,##0.000000");
storage.getRangeByIndexes(1,5,storageRows.length,1).setNumberFormat("#,##0.000000");
storage.freezePanes.freezeRows(1);

emergency.getRange("A2:C11").clear({applyTo:"contents"});
const emergencyRows=payload.emergency.map(row=>row.map((value,col)=>
  col===0 && value!==null ? new Date(`${value}T00:00:00Z`) : value));
emergency.getRangeByIndexes(1,0,emergencyRows.length,3).values=emergencyRows;
emergency.getRangeByIndexes(1,0,emergencyRows.length,1).setNumberFormat("yyyy-mm-dd");
emergency.getRangeByIndexes(1,2,emergencyRows.length,1).setNumberFormat("#,##0.000000");
emergency.getRangeByIndexes(1,0,emergencyRows.length,3).format.borders={
  preset:"all",style:"thin",color:"#9CA3AF"};
emergency.freezePanes.freezeRows(1);

wb.recalculate();
for (const [sheet,range,file] of [
  ["计划购电量","A1:D6","plan_preview.png"],
  ["调整购电量","A1:D6","adjusted_preview.png"],
  ["充放电量","A1:F9","storage_preview.png"],
  ["紧急购电量","A1:C9","emergency_preview.png"],
]) {
  const preview=await wb.render({sheetName:sheet,range,scale:1.5,format:"png"});
  await fs.writeFile(new URL(file,base),new Uint8Array(await preview.arrayBuffer()));
}
console.log((await wb.inspect({kind:"region",sheetId:"计划购电量",range:"A1:D4",maxChars:1600})).ndjson);
console.log((await wb.inspect({kind:"region",sheetId:"充放电量",range:"A1:F8",maxChars:2200})).ndjson);
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(fileURLToPath(new URL("result3.xlsx",base)));
console.log(JSON.stringify({output:fileURLToPath(new URL("result3.xlsx",base)),
  storageRows:storageRows.length,emergencyRows:emergencyRows.length}));
