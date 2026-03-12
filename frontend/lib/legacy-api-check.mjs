const legacyApiPattern = /\/api\/(?!v1\/|auth(?:\/|$)|sse(?:\/|$))/g;
const allowedInternalApiPatterns = [
  /\/api\/audits\/[^"'`\s?#),]+\/download-pdf(?:\?[^"'`\s)#,]*)?(?=$|["'`\s)#,])/g,
];

function collectMatchRanges(line, patterns) {
  return patterns.flatMap((pattern) => {
    pattern.lastIndex = 0;
    return Array.from(line.matchAll(pattern), (match) => ({
      start: match.index ?? 0,
      end: (match.index ?? 0) + match[0].length,
    }));
  });
}

function isWithinAllowedRange(index, allowedRanges) {
  return allowedRanges.some(
    (allowedRange) => index >= allowedRange.start && index < allowedRange.end,
  );
}

export function findLegacyApiMatches(line) {
  const allowedRanges = collectMatchRanges(line, allowedInternalApiPatterns);
  legacyApiPattern.lastIndex = 0;

  return Array.from(line.matchAll(legacyApiPattern)).filter(
    (match) => !isWithinAllowedRange(match.index ?? 0, allowedRanges),
  );
}

export function hasLegacyApiViolation(line) {
  return findLegacyApiMatches(line).length > 0;
}
