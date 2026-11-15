import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';
import { analyzeProcessFlowReferences, composeFlowName } from '../..';
import { collectProcessFlowReferences } from '..';

const fixture = JSON.parse(
  readFileSync(
    join(
      __dirname,
      '../../../tests/fixtures/process-flow-reference-name.v1.json'
    ),
    'utf8'
  )
);

for (const example of fixture.composition) {
  test(`compose Flow name: ${example.name}`, () => {
    const before = structuredClone(example.fields);
    const result = composeFlowName(example.fields);
    assert.deepEqual(result.description, example.description);
    assert.deepEqual(
      result.issues.map((issue) => issue.code),
      example.codes
    );
    assert.deepEqual(example.fields, before);
  });
}

for (const example of fixture.checks) {
  test(`check Process Flow reference: ${example.name}`, () => {
    const flows = example.evidence.map((key: string) => fixture.flows[key]);
    const before = structuredClone({ process: example.process, flows });
    const result = analyzeProcessFlowReferences(example.process, { flows });
    assert.equal(result.profile, fixture.profile);
    assert.equal(result.complete, !example.statuses.includes('unresolved'));
    assert.equal(result.valid, example.codes.length === 0);
    assert.deepEqual(
      result.coverage.map((check) => check.status),
      example.statuses
    );
    assert.deepEqual(
      result.validationIssues.map((issue) => issue.code),
      example.codes
    );
    if (example.paths)
      assert.deepEqual(
        result.validationIssues.map((issue) => issue.path),
        example.paths
      );
    const refs = collectProcessFlowReferences(example.process);
    assert.deepEqual(
      refs.map(({ path }) => path),
      result.coverage
        .filter(({ status }) => status !== 'not-applicable')
        .map(({ path }) => path)
    );
    assert.deepEqual({ process: example.process, flows }, before);
  });
}
