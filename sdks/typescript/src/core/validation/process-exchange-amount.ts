/** Compare the two inventory amounts before any conversion to a floating-point quantity. */
function decimalParts(value: unknown) {
  if (
    typeof value !== 'string' &&
    !(typeof value === 'number' && Number.isFinite(value))
  ) {
    return undefined;
  }
  const token = String(value);
  const match = /^([+-]?)(\d*)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/.exec(token);
  if (!match || match[0] !== token || !(match[2] || match[3])) return undefined;

  const fraction = match[3] ?? '';
  const digits = (match[2] + fraction).replace(/^0+/, '');
  if (!digits) return { original: value, coefficient: '0', exponent: 0n };
  let end = digits.length;
  while (digits[end - 1] === '0') end--;
  return {
    original: value,
    coefficient: (match[1] === '-' ? '-' : '') + digits.slice(0, end),
    exponent:
      BigInt(match[4] ?? '0') + BigInt(digits.length - end - fraction.length),
  };
}

export function findProcessExchangeAmountConflict(exchange: {
  meanAmount?: unknown;
  resultingAmount?: unknown;
  referenceToVariable?: unknown;
}) {
  const { meanAmount, resultingAmount, referenceToVariable } = exchange;
  if (
    referenceToVariable != null &&
    (typeof referenceToVariable !== 'string' ||
      referenceToVariable.trim() !== '')
  )
    return undefined;
  const mean = decimalParts(meanAmount);
  const result = decimalParts(resultingAmount);
  if (
    !mean ||
    !result ||
    (mean.coefficient === result.coefficient &&
      mean.exponent === result.exponent)
  )
    return undefined;
  return {
    code: 'process_exchange_amount_conflict' as const,
    meanAmount: mean.original,
    resultingAmount: result.original,
    message: `Without a variable, resultingAmount (${String(result.original)}) must equal meanAmount (${String(mean.original)}).`,
  };
}
