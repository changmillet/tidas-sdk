import { duplicateLocalizedLanguages, jsonValuesEqual } from './json-schema';
import type { CoverageStatus, SemanticPath } from './process-semantics';
import { TIDAS_LANGUAGE_CODE_SET } from './tidas-languages';

export const PROCESS_FLOW_REFERENCE_NAME_PROFILE =
  'tidas.process-flow-reference-name.v1';
const nameFields = [
  'baseName',
  'treatmentStandardsRoutes',
  'mixAndLocationTypes',
  'flowProperties',
] as const;
const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const versionPattern = /^[0-9]{2}\.[0-9]{2}(\.[0-9]{3})?$/;
const maxDescriptionLength = 1000;

export interface FlowNameText {
  '@xml:lang': string;
  '#text': string;
}

export interface ExactFlowNameEvidence {
  uuid: string;
  version: string;
  /** Raw TIDAS Flow document verified by the caller for access and content. */
  document: unknown;
}

export type FlowReferenceNameIssueCode =
  | 'duplicate_language_entry'
  | 'flow_name_text_invalid'
  | 'flow_name_base_missing'
  | 'flow_name_translation_missing'
  | 'flow_name_too_long'
  | 'flow_reference_inexact'
  | 'flow_reference_evidence_unavailable'
  | 'flow_reference_evidence_invalid'
  | 'flow_reference_evidence_conflict'
  | 'flow_reference_version_mismatch'
  | 'flow_reference_description_mismatch';

export interface FlowReferenceNameIssue {
  code: FlowReferenceNameIssueCode;
  path: SemanticPath;
  severity: 'error';
  params: Record<string, string | number>;
  message: string;
  rawCode: 'process_flow_reference_name';
}

export interface ProcessFlowReference {
  path: SemanticPath;
  uuid: string;
  version: string;
  description: unknown;
}

const object = (value: unknown): Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
const present = (value: unknown) => value !== undefined;
const entries = (value: unknown, path: SemanticPath) =>
  Array.isArray(value)
    ? value.map((item, index) => ({ value: item, path: [...path, index] }))
    : present(value)
      ? [{ value, path }]
      : [];

function issue(
  code: FlowReferenceNameIssueCode,
  path: SemanticPath,
  message: string,
  params: FlowReferenceNameIssue['params'] = {}
): FlowReferenceNameIssue {
  return {
    code,
    path,
    message,
    params,
    severity: 'error',
    rawCode: 'process_flow_reference_name',
  };
}

function normalizeText(text: string) {
  // Use exactly XML whitespace in both runtimes. Preserve inner text and punctuation.
  const whitespace = ' \t\r\n';
  let start = 0;
  let end = text.length;
  while (start < end && whitespace.includes(text.charAt(start))) start++;
  while (end > start && whitespace.includes(text.charAt(end - 1))) end--;
  return text.slice(start, end).normalize('NFC');
}

function readLocalized(
  raw: unknown,
  path: SemanticPath,
  issues: FlowReferenceNameIssue[]
): Map<string, string> {
  const result = new Map<string, string>();
  for (const { language, index, firstIndex } of duplicateLocalizedLanguages(
    Array.isArray(raw) ? raw : []
  )) {
    issues.push(
      issue(
        'duplicate_language_entry',
        [...path, index, '@xml:lang'],
        `Language ${language} already occurs at index ${firstIndex} in this field.`,
        { language, firstIndex }
      )
    );
  }
  for (const item of entries(raw, path)) {
    const value = object(item.value);
    const language = value['@xml:lang'];
    const text = value['#text'];
    if (
      typeof language !== 'string' ||
      !TIDAS_LANGUAGE_CODE_SET.has(language) ||
      typeof text !== 'string'
    ) {
      issues.push(
        issue(
          'flow_name_text_invalid',
          item.path,
          'A supported language and text are required.'
        )
      );
      continue;
    }
    if (!result.has(language)) result.set(language, normalizeText(text));
  }
  return result;
}

function usable(text: string | undefined): text is string {
  return text !== undefined && text !== '' && text !== '-';
}

/** Compose the four localized fields of a raw TIDAS Flow name, without fallback. */
export function composeFlowName(name: unknown) {
  const issues: FlowReferenceNameIssue[] = [];
  const data = object(name);
  const [base, ...qualifiers] = nameFields.map((field) =>
    readLocalized(data[field], [field], issues)
  );
  const languages = new Set(base.keys());
  for (const qualifier of qualifiers) {
    for (const [language, text] of qualifier)
      if (usable(text)) languages.add(language);
  }
  if (!languages.size) {
    issues.push(
      issue(
        'flow_name_base_missing',
        ['baseName'],
        'A substantive Flow base name is required.'
      )
    );
  }
  const description: FlowNameText[] = [];
  for (const language of [...languages].sort()) {
    const baseText = base.get(language);
    if (!usable(baseText)) {
      issues.push(
        issue(
          'flow_name_base_missing',
          ['baseName'],
          'Missing substantive Flow base name for this language.',
          { language }
        )
      );
      continue;
    }
    const parts = [baseText];
    qualifiers.forEach((qualifier, index) => {
      const text = qualifier.get(language);
      if (usable(text)) parts.push(text);
      else if ([...qualifier.values()].some(usable)) {
        const field = nameFields[index + 1];
        issues.push(
          issue(
            'flow_name_translation_missing',
            [field],
            'A populated Flow name segment lacks this translation.',
            { language, field }
          )
        );
      }
    });
    const text = parts.join('; ');
    const length = Array.from(text).length;
    if (length > maxDescriptionLength) {
      issues.push(
        issue(
          'flow_name_too_long',
          [],
          'The full Flow name exceeds the reference description limit.',
          { language, length, maximum: maxDescriptionLength }
        )
      );
    }
    description.push({ '@xml:lang': language, '#text': text });
  }
  return { description: issues.length ? [] : description, issues };
}

/** Enumerate every exchange reference and its exact path, including invalid identities. */
export function collectProcessFlowReferences(
  process: unknown
): ProcessFlowReference[] {
  const processData = object(object(process).processDataSet);
  const collectionPath = ['processDataSet', 'exchanges', 'exchange'];
  return entries(
    object(processData.exchanges).exchange,
    collectionPath
  ).flatMap(({ value, path }) => {
    const referencePath = [...path, 'referenceToFlowDataSet'];
    const refs = entries(object(value).referenceToFlowDataSet, referencePath);
    if (!refs.length) refs.push({ value: undefined, path: referencePath });
    return refs.map((entry) => {
      const ref = object(entry.value);
      const uuid = ref['@refObjectId'];
      const version = ref['@version'];
      return {
        path: entry.path,
        uuid: typeof uuid === 'string' ? uuid : '',
        version: typeof version === 'string' ? version : '',
        description: ref['common:shortDescription'],
      };
    });
  });
}

export interface ProcessFlowReferenceNameCheck {
  path: SemanticPath;
  uuid: string;
  version: string;
  status: CoverageStatus;
  expectedDescription?: FlowNameText[];
}

type BoundName = ReturnType<typeof composeFlowName>;
type Evidence = {
  document: unknown;
  name?: BoundName;
  error?: FlowReferenceNameIssueCode;
};

function bindName({
  uuid,
  version,
  document,
}: ExactFlowNameEvidence): Evidence {
  const root = object(object(document).flowDataSet);
  const info = object(object(root.flowInformation).dataSetInformation);
  const publication = object(
    object(root.administrativeInformation).publicationAndOwnership
  );
  if (
    typeof info['common:UUID'] !== 'string' ||
    typeof publication['common:dataSetVersion'] !== 'string'
  ) {
    return { document, error: 'flow_reference_evidence_invalid' };
  }
  if (info['common:UUID'] !== uuid)
    return { document, error: 'flow_reference_evidence_invalid' };
  if (publication['common:dataSetVersion'] !== version) {
    return { document, error: 'flow_reference_version_mismatch' };
  }
  return { document, name: composeFlowName(info.name) };
}

export interface ProcessFlowReferenceNameAnalysis {
  profile: typeof PROCESS_FLOW_REFERENCE_NAME_PROFILE;
  complete: boolean;
  valid: boolean;
  coverage: ProcessFlowReferenceNameCheck[];
  validationIssues: FlowReferenceNameIssue[];
}

/** Compare each description using explicit, exact Flow evidence. Never fetch or mutate data. */
export function analyzeProcessFlowReferences(
  process: unknown,
  options: { flows?: readonly ExactFlowNameEvidence[] } = {}
): ProcessFlowReferenceNameAnalysis {
  const byIdentity = new Map<string, Evidence>();
  const knownUuids = new Set<string>();
  for (const evidence of options.flows ?? []) {
    const key = JSON.stringify([evidence.uuid, evidence.version]);
    const earlier = byIdentity.get(key);
    if (!earlier) byIdentity.set(key, bindName(evidence));
    else if (!jsonValuesEqual(earlier.document, evidence.document)) {
      byIdentity.set(key, {
        document: earlier.document,
        error: 'flow_reference_evidence_conflict',
      });
    }
    knownUuids.add(evidence.uuid);
  }
  const validationIssues: FlowReferenceNameIssue[] = [];
  const coverage = collectProcessFlowReferences(process).map(
    ({ path, uuid, version, description }) => {
      const identity = { uuid, version };
      const scope = { path, ...identity };
      const report = (
        status: CoverageStatus,
        code: FlowReferenceNameIssueCode,
        message: string
      ) => {
        validationIssues.push(issue(code, path, message, identity));
        return { ...scope, status };
      };
      if (!uuidPattern.test(uuid) || !versionPattern.test(version)) {
        return report(
          'invalid',
          'flow_reference_inexact',
          'Flow reference requires an exact UUID and version.'
        );
      }
      const evidence = byIdentity.get(JSON.stringify([uuid, version]));
      if (!evidence) {
        const code = knownUuids.has(uuid)
          ? 'flow_reference_version_mismatch'
          : 'flow_reference_evidence_unavailable';
        return report(
          'unresolved',
          code,
          'Evidence for the selected Flow version was not supplied.'
        );
      }
      if (evidence.error) {
        return report(
          'unresolved',
          evidence.error,
          'Supplied Flow evidence is invalid or conflicting for this reference.'
        );
      }
      const composed = evidence.name;
      if (!composed || composed.issues.length) {
        for (const finding of composed?.issues ?? []) {
          validationIssues.push({
            ...finding,
            path,
            params: {
              ...finding.params,
              ...identity,
              flowNamePath: finding.path.join('.'),
            },
          });
        }
        return { ...scope, status: 'unresolved' as const };
      }
      const expectedDescription = composed.description;
      const descriptionPath = [...path, 'common:shortDescription'];
      const findings: FlowReferenceNameIssue[] = [];
      const actual = readLocalized(description, descriptionPath, findings);
      const expected = new Map(
        expectedDescription.map((item) => [item['@xml:lang'], item['#text']])
      );
      if (!findings.length) {
        for (const language of [
          ...new Set([...expected.keys(), ...actual.keys()]),
        ].sort()) {
          if (expected.get(language) === actual.get(language)) continue;
          findings.push(
            issue(
              'flow_reference_description_mismatch',
              descriptionPath,
              'The exchange description differs from the selected Flow name.',
              {
                ...identity,
                language,
                expected: expected.get(language) ?? '',
                actual: actual.get(language) ?? '',
              }
            )
          );
        }
      }
      validationIssues.push(
        ...findings.map((finding) => ({
          ...finding,
          params: { ...finding.params, ...identity },
        }))
      );
      return {
        ...scope,
        expectedDescription,
        status: findings.length ? ('invalid' as const) : ('passed' as const),
      };
    }
  );
  if (!coverage.length) {
    coverage.push({
      path: ['processDataSet', 'exchanges', 'exchange'],
      uuid: '',
      version: '',
      status: 'not-applicable',
    });
  }
  return {
    profile: PROCESS_FLOW_REFERENCE_NAME_PROFILE,
    complete: coverage.every(({ status }) => status !== 'unresolved'),
    valid: validationIssues.length === 0,
    coverage,
    validationIssues,
  };
}
