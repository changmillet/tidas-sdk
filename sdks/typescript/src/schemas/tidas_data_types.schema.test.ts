import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { z } from 'zod';
import {
  AnnualSupplyOrProductionVolumeMultiLangSchema,
  AnnualSupplyOrProductionVolumeTextItemSchema,
  CASNumberSchema,
  CommonOtherSchema,
  FTMultiLangSchema,
  GlobalReferenceTypeSchema,
  RequiredFTMultiLangSchema,
  RequiredSTMultiLangSchema,
  RequiredStringMultiLangSchema,
  STMultiLangSchema,
  StringMultiLangSchema,
  TidasLanguageCodeSchema,
  LocalizedTextItemSchema,
} from './tidas_data_types.schema';
import { ValidationUtils } from '../core/config/ValidationConfig';
import { createContact } from '../core/factories';

describe('CASNumberSchema', () => {
  it('accepts CAS numbers with a valid check digit', () => {
    assert.strictEqual(CASNumberSchema.safeParse('64-17-5').success, true);
    assert.strictEqual(CASNumberSchema.safeParse('007732-18-5').success, true);
  });

  it('rejects invalid format and invalid check digits', () => {
    assert.strictEqual(CASNumberSchema.safeParse('2023600').success, false);

    const result = CASNumberSchema.safeParse('64-17-6');

    assert.strictEqual(result.success, false);
    if (!result.success) {
      assert.strictEqual(
        ValidationUtils.normalizeIssues(result.error.issues)[0]?.code,
        'cas_number_checksum_error'
      );
    }
  });
});

describe('CommonOtherSchema', () => {
  it('accepts namespace declarations plus non-common extension elements', () => {
    const result = CommonOtherSchema.safeParse({
      '@xmlns:ext': 'https://example.com/tidas/extensions',
      'ext:note': {
        '#text': 'Carbon dioxide',
        '@xml:lang': 'en',
      },
    });

    assert.strictEqual(result.success, true);
  });

  it('rejects legacy string common:other values', () => {
    const result = CommonOtherSchema.safeParse('Carbon dioxide');

    assert.strictEqual(result.success, false);
  });

  it('rejects namespace-only and common-prefixed entries', () => {
    assert.strictEqual(
      CommonOtherSchema.safeParse({
        '@xmlns:ext': 'https://example.com/tidas/extensions',
      }).success,
      false
    );

    assert.strictEqual(
      CommonOtherSchema.safeParse({
        'common:note': 'Carbon dioxide',
      }).success,
      false
    );
  });
});

describe('LocalizedTextItemSchema', () => {
  it('accepts TIDAS language enumeration values', () => {
    assert.strictEqual(TidasLanguageCodeSchema.safeParse('en').success, true);
    assert.strictEqual(TidasLanguageCodeSchema.safeParse('de').success, true);
    assert.strictEqual(TidasLanguageCodeSchema.safeParse('zh').success, true);
    assert.strictEqual(
      LocalizedTextItemSchema.safeParse({
        '@xml:lang': 'de',
        '#text': 'Deutscher Titel',
      }).success,
      true
    );
  });

  it('rejects language codes outside the TIDAS enumeration', () => {
    const result = LocalizedTextItemSchema.safeParse({
      '@xml:lang': 'en-US',
      '#text': 'English title',
    });

    assert.strictEqual(result.success, false);
    if (!result.success) {
      assert.strictEqual(
        ValidationUtils.normalizeIssues(result.error.issues)[0]?.code,
        'localized_text_language_not_in_tidas_enum'
      );
    }
  });

  it('checks scripts only for exact zh and en language codes', () => {
    assert.strictEqual(
      LocalizedTextItemSchema.safeParse({
        '@xml:lang': 'zh',
        '#text': 'English only',
      }).success,
      false
    );
    assert.strictEqual(
      LocalizedTextItemSchema.safeParse({
        '@xml:lang': 'en',
        '#text': '中文',
      }).success,
      false
    );
  });
});

describe('AnnualSupplyOrProductionVolumeMultiLangSchema', () => {
  it('accepts localized annual volume text with numeric prefix and suffix', () => {
    assert.strictEqual(
      AnnualSupplyOrProductionVolumeTextItemSchema.safeParse({
        '@xml:lang': 'en',
        '#text': '12.5 kg reference flow',
      }).success,
      true
    );

    assert.strictEqual(
      AnnualSupplyOrProductionVolumeMultiLangSchema.safeParse([
        {
          '@xml:lang': 'en',
          '#text': '12.5 kg reference flow',
        },
      ]).success,
      true
    );
  });

  it('rejects numeric text without suffix context', () => {
    assert.strictEqual(
      AnnualSupplyOrProductionVolumeTextItemSchema.safeParse({
        '@xml:lang': 'en',
        '#text': '12.5',
      }).success,
      false
    );
  });
});

describe('localized language uniqueness', () => {
  it('keeps a duplicate language path when another item in the same list is malformed', () => {
    const schema = z.object({ comments: FTMultiLangSchema });
    const result = schema.safeParse({
      comments: [
        { '@xml:lang': 'en', '#text': 'First' },
        { '@xml:lang': 'en', '#text': 'Second' },
        { '@xml:lang': 'not-a-language', '#text': 'Third' },
      ],
    });
    assert.equal(result.success, false);
    assert.deepEqual(
      ValidationUtils.normalizeIssues(result.error.issues)
        .filter((issue) => issue.code === 'duplicate_language_entry')
        .map((issue) => issue.path),
      [['comments', 1, '@xml:lang']]
    );
  });

  it('keeps localized reference fields independent and ignores opaque extension arrays', () => {
    const schema = z.object({
      references: GlobalReferenceTypeSchema,
      other: CommonOtherSchema,
    });
    const reference = (id: string, description: string) => ({
      '@type': 'source data set',
      '@refObjectId': id,
      '@version': '01.00.000',
      '@uri': '',
      '@xml:lang': 'en',
      '#text': 'Reference metadata',
      'common:shortDescription': [{ '@xml:lang': 'en', '#text': description }],
    });
    const first = reference(
      '00000000-0000-4000-8000-000000000001',
      'First source'
    );
    const second = reference(
      '00000000-0000-4000-8000-000000000002',
      'Second source'
    );
    const other = {
      '@xmlns:example': 'https://example.com/tidas',
      'example:labels': [
        { '@xml:lang': 'en', '#text': 'First' },
        { '@xml:lang': 'en', '#text': 'Second' },
      ],
    };
    assert.equal(
      schema.safeParse({ references: [first, second], other }).success,
      true
    );
    second['common:shortDescription'].push({
      '@xml:lang': 'en',
      '#text': 'Duplicate',
    });
    const result = schema.safeParse({ references: [first, second], other });
    assert.equal(result.success, false);
    assert.deepEqual(
      ValidationUtils.normalizeIssues(result.error.issues)
        .filter((issue) => issue.code === 'duplicate_language_entry')
        .map((issue) => issue.path),
      [['references', 1, 'common:shortDescription', 1, '@xml:lang']]
    );
  });

  it('preserves the entity snapshot and exposes the same code and path via validateEnhanced', () => {
    const contact = createContact(undefined, {
      mode: 'strict',
      deepValidation: true,
    });
    contact.contactDataSet.contactInformation.dataSetInformation[
      'common:name'
    ] = [
      { '@xml:lang': 'en', '#text': 'First name' },
      { '@xml:lang': 'en', '#text': 'Second name' },
    ];
    const before = JSON.stringify(contact.toJSON());
    const result = contact.validateEnhanced();
    assert.equal(result.success, false);
    assert.deepEqual(
      result.validationIssues
        .filter((issue) => issue.code === 'duplicate_language_entry')
        .map((issue) => issue.path),
      [
        [
          'contactDataSet',
          'contactInformation',
          'dataSetInformation',
          'common:name',
          1,
          '@xml:lang',
        ],
      ]
    );
    assert.equal(JSON.stringify(contact.toJSON()), before);
  });

  for (const [name, schema] of [
    ['FT', FTMultiLangSchema],
    ['required FT', RequiredFTMultiLangSchema],
    ['ST', STMultiLangSchema],
    ['required ST', RequiredSTMultiLangSchema],
    ['String', StringMultiLangSchema],
    ['required String', RequiredStringMultiLangSchema],
    ['annual supply', AnnualSupplyOrProductionVolumeMultiLangSchema],
  ] as const) {
    it(`checks languages within ${name} and preserves whole-item uniqueness`, () => {
      const first = { '@xml:lang': 'en', '#text': '1 kg annual supply' };
      const second = {
        '@xml:lang': 'en',
        '#text': '2 kg annual supply',
        '@extra': 'kept in input',
      };
      const third = { '@xml:lang': 'de', '#text': '1 kg Jahresmenge' };
      assert.equal(schema.safeParse(first).success, true);
      assert.equal(schema.safeParse([first, third]).success, true);

      const value = [first, second, third, { ...third }];
      const original = structuredClone(value);
      const result = schema.safeParse(value);
      assert.equal(result.success, false);
      const issues = ValidationUtils.normalizeIssues(result.error.issues);
      assert.deepEqual(
        issues
          .filter((issue) => issue.code === 'duplicate_language_entry')
          .map(({ path, params }) => ({ path, params })),
        [
          { path: [1, '@xml:lang'], params: { language: 'en', firstIndex: 0 } },
          { path: [3, '@xml:lang'], params: { language: 'de', firstIndex: 2 } },
        ]
      );
      assert.ok(
        issues.some(
          (issue) =>
            issue.message === 'Array items must be unique' &&
            issue.path.length === 1 &&
            issue.path[0] === 3
        )
      );
      assert.deepEqual(value, original);
    });
  }
});
