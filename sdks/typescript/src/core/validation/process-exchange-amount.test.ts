import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import {
  ProcessSchema,
  createProcess,
  findProcessExchangeAmountConflict,
} from '../../index';

const fixture = (file: string) =>
  JSON.parse(
    readFileSync(
      path.resolve(__dirname, '../../../../../test-data', file),
      'utf8'
    )
  );
const base = fixture('process-exchange-amount-control.json');
for (const { conflict, ...values } of fixture(
  'process-exchange-amount-cases.json'
)) {
  test('Process exchange amounts ' + JSON.stringify(values), () => {
    const data = structuredClone(base);
    const rows = data.processDataSet.exchanges.exchange;
    rows.push({ ...rows[0], '@dataSetInternalID': '2', ...values });
    const before = structuredClone(data);
    const rule = findProcessExchangeAmountConflict(values);
    assert.equal(Boolean(rule), conflict);
    const result = ProcessSchema.safeParse(data);
    const enhanced = createProcess(structuredClone(data)).validateEnhanced();
    assert.equal(result.success, !conflict);
    assert.equal(enhanced.success, !conflict);
    if (conflict) {
      const fault = enhanced.validationIssues.find(
        (i) => i.code === 'process_exchange_amount_conflict'
      );
      assert.deepEqual(fault?.path, [
        'processDataSet',
        'exchanges',
        'exchange',
        1,
        'resultingAmount',
      ]);
      assert.deepEqual(fault.params, {
        meanAmount: values.meanAmount,
        resultingAmount: values.resultingAmount,
      });
    }
    assert.deepEqual(data, before);
  });
}

test('partial legacy records preserve supported scalar handling', () => {
  assert.equal(
    findProcessExchangeAmountConflict({
      meanAmount: 1,
      resultingAmount: '1.0',
    }),
    undefined
  );
  assert.equal(
    findProcessExchangeAmountConflict({ meanAmount: 1, resultingAmount: 4 })
      ?.resultingAmount,
    4
  );
  for (const value of [undefined, null, NaN, Infinity, '', '.', '0x01', '2x']) {
    assert.equal(
      findProcessExchangeAmountConflict({
        meanAmount: value,
        resultingAmount: '1',
      }),
      undefined
    );
  }
});
