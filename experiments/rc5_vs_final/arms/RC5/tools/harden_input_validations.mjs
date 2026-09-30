#!/usr/bin/env node
/*
 * RC9.2.2 workbook repair utility.
 *
 * Uses the public artifact-tool API to rebuild imported Excel validation
 * collections without changing workbook values, formulas, or the parsed
 * scheduling contract. Excel validations are emitted as explicit error
 * alerts so a typed value outside a dropdown/range is rejected visibly.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const [inputArg, outputArg] = process.argv.slice(2);
if (!inputArg || !outputArg) throw new Error('Usage: harden_input_validations.mjs INPUT_DIR OUTPUT_DIR');
const inputDir = path.resolve(inputArg);
const outputDir = path.resolve(outputArg);
await fs.mkdir(outputDir, { recursive: true });

const typeMap = { 1: 'whole', 2: 'whole', 3: 'decimal', 4: 'list', 5: 'date', 6: 'time', 7: 'textLength', 8: 'custom' };
const operatorMap = { 0: 'between', 1: 'between', 2: 'notBetween', 3: 'equalTo', 4: 'notEqualTo', 5: 'greaterThan', 6: 'lessThan', 7: 'greaterThanOrEqual', 8: 'lessThanOrEqual' };

function makeRule(item) {
  const type = typeof item.type === 'string' ? item.type : (typeMap[item.type] || 'custom');
  const rule = { type };
  if (item.operator !== undefined && item.operator !== null) {
    rule.operator = typeof item.operator === 'string' ? item.operator : (operatorMap[item.operator] || 'between');
  }
  if (item.formula1 !== undefined && item.formula1 !== null && item.formula1 !== '') rule.formula1 = item.formula1;
  if (item.formula2 !== undefined && item.formula2 !== null && item.formula2 !== '') rule.formula2 = item.formula2;
  return rule;
}

function rangesFromSqref(sqref) {
  return String(sqref || '').trim().split(/\s+/).filter(Boolean);
}

let total = 0;
for (const name of (await fs.readdir(inputDir)).filter(n => n.toLowerCase().endsWith('.xlsx')).sort()) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(inputDir, name)));
  let count = 0;
  for (const sheet of workbook.worksheets.items) {
    const items = [...(sheet.dataValidations?.items ?? [])];
    if (sheet.dataValidations) sheet.dataValidations.items.length = 0;
    for (const item of items) {
      for (const address of rangesFromSqref(item.sqref)) {
        sheet.dataValidations.add({ range: address, rule: makeRule(item) });
        const added = sheet.dataValidations.items[sheet.dataValidations.items.length - 1];
        added.allowBlank = item.allowBlank !== false;
        added.showDropDown = item.showDropDown === true;
        added.showInputMessage = item.showInputMessage === true;
        added.showErrorMessage = true;
        if (item.promptTitle) added.promptTitle = item.promptTitle;
        if (item.promptMessage) added.promptMessage = item.promptMessage;
        added.errorTitle = 'Invalid input';
        added.error = 'This value is not allowed. Select a dropdown value or correct the entered number/time.';
        count += 1;
      }
    }
  }
  workbook.recalculate();
  const output = path.join(outputDir, name);
  await (await SpreadsheetFile.exportXlsx(workbook)).save(output);
  console.log(JSON.stringify({ workbook: name, hardened_validations: count, output }));
  total += count;
}
console.log(JSON.stringify({ status: 'PASS', total_validations: total }));
