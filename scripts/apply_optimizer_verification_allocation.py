from pathlib import Path

path = Path("public/optimizer-worker.js")
text = path.read_text(encoding="utf-8")

old_add = r'''function addUniqueRanked(output, seen, records, count, source, objective) {
  let added = 0;
  const sorted = [...records].sort(
    (left, right) => compareRecords(left, right, objective),
  );
  for (const record of sorted) {
    if (added >= count) break;
    if (seen.has(record.mask)) continue;
    seen.add(record.mask);
    output.push({ ...record, selectionSource: source });
    added += 1;
  }
}'''
new_add = r'''function addUniqueRanked(output, seen, records, count, source, objective) {
  let added = 0;
  const sorted = [...records].sort(
    (left, right) => compareRecords(left, right, objective),
  );
  for (const record of sorted) {
    if (added >= count) break;
    if (seen.has(record.mask)) continue;
    seen.add(record.mask);
    output.push({ ...record, selectionSource: source });
    added += 1;
  }
  return added;
}'''
if text.count(old_add) != 1:
    raise SystemExit(f"addUniqueRanked matches={text.count(old_add)}")
text = text.replace(old_add, new_add, 1)

start = text.index("function selectVerificationRecords(")
end = text.index("\n\nexport function serializeMasksLittleEndian", start)
replacement = r'''function selectVerificationRecords(records, primaryObjective) {
  const output = [];
  const seen = new Set();
  const requested = Object.fromEntries(
    OBJECTIVES.map((objective) => [
      objective,
      objective === primaryObjective ? 120 : 30,
    ]),
  );
  requested.pareto_diversity = 60;
  const actual = Object.fromEntries(
    [...OBJECTIVES, "pareto_diversity"].map((key) => [key, 0]),
  );

  actual[primaryObjective] = addUniqueRanked(
    output,
    seen,
    records,
    requested[primaryObjective],
    `primary:${primaryObjective}`,
    primaryObjective,
  );
  for (const objective of OBJECTIVES) {
    if (objective === primaryObjective) continue;
    actual[objective] = addUniqueRanked(
      output,
      seen,
      records,
      requested[objective],
      `secondary:${objective}`,
      objective,
    );
  }

  const anchors = output.slice(0, 20).map((record) => record.mask);
  const diversityDistance = (record) => Math.min(
    ...anchors.map((anchor) => hammingDistance(record.mask, anchor)),
  );
  const pareto = approximatePareto(records)
    .filter((record) => !seen.has(record.mask))
    .sort((left, right) => (
      diversityDistance(right) - diversityDistance(left)
      || compareRecords(left, right, primaryObjective)
      || left.mask - right.mask
    ));
  const remaining = records
    .filter((record) => !seen.has(record.mask))
    .sort((left, right) => (
      diversityDistance(right) - diversityDistance(left)
      || compareRecords(left, right, primaryObjective)
      || left.mask - right.mask
    ));
  for (const record of [...pareto, ...remaining]) {
    if (actual.pareto_diversity >= requested.pareto_diversity) break;
    if (seen.has(record.mask)) continue;
    seen.add(record.mask);
    output.push({ ...record, selectionSource: "pareto-diversity" });
    actual.pareto_diversity += 1;
  }

  const mismatches = [...OBJECTIVES, "pareto_diversity"].filter(
    (key) => actual[key] !== requested[key],
  );
  if (output.length !== 300 || mismatches.length) {
    throw new Error(
      `精確複驗配額不完整：${JSON.stringify({ requested, actual })}`,
    );
  }
  return {
    records: output,
    allocation: { requested, actual },
  };
}'''
text = text[:start] + replacement + text[end:]
text = text.replace(
    '''  const verificationRecords = selectVerificationRecords(deepRecords, primaryObjective);
  const evaluatedMaskHash = await digestMasks(selection.masks);
  return {
    combinations: verificationRecords.map((record, index) => ({''',
    '''  const verificationSelection = selectVerificationRecords(
    deepRecords,
    primaryObjective,
  );
  const verificationRecords = verificationSelection.records;
  const evaluatedMaskHash = await digestMasks(selection.masks);
  return {
    combinations: verificationRecords.map((record, index) => ({''',
    1,
)
text = text.replace(
    '''      budgetAllocation: selection.allocation,
      localSearchTrace: selection.trace,''',
    '''      budgetAllocation: selection.allocation,
      exactVerificationAllocation: verificationSelection.allocation,
      localSearchTrace: selection.trace,''',
    1,
)
path.write_text(text, encoding="utf-8")

test_path = Path("tests/test_optimizer_worker.mjs")
test_text = test_path.read_text(encoding="utf-8")
test_text = test_text.replace(
    '''  assert.equal(result.combinations.length, 300);
  assert.equal(new Set(result.combinations.map((item) => item.mask)).size, 300);''',
    '''  assert.deepEqual(result.search.exactVerificationAllocation, {
    requested: {
      sortino_ratio: 120,
      cagr: 30,
      mdd_abs: 30,
      beta_abs: 30,
      alpha: 30,
      pareto_diversity: 60,
    },
    actual: {
      sortino_ratio: 120,
      cagr: 30,
      mdd_abs: 30,
      beta_abs: 30,
      alpha: 30,
      pareto_diversity: 60,
    },
  });
  assert.equal(result.combinations.length, 300);
  assert.equal(new Set(result.combinations.map((item) => item.mask)).size, 300);
  const sourceCounts = Object.groupBy(
    result.combinations,
    (item) => item.selectionSource,
  );
  assert.equal(sourceCounts["primary:sortino_ratio"].length, 120);
  assert.equal(sourceCounts["secondary:cagr"].length, 30);
  assert.equal(sourceCounts["secondary:mdd_abs"].length, 30);
  assert.equal(sourceCounts["secondary:beta_abs"].length, 30);
  assert.equal(sourceCounts["secondary:alpha"].length, 30);
  assert.equal(sourceCounts["pareto-diversity"].length, 60);''',
    1,
)
test_path.write_text(test_text, encoding="utf-8")

doc = Path("docs/PORTFOLIO_OPTIMIZER_MVP.md")
doc.write_text(
    doc.read_text(encoding="utf-8")
    + "\n精確複驗輸出必須同時保存 requested 與 actual 配額；Pareto 點不足 60 時，以對既有入選組合成分差異最大的未入選組合補足，仍歸類為 Pareto／多樣性，不得改由主要目標排名補足。\n",
    encoding="utf-8",
)
Path("scripts/apply_optimizer_verification_allocation.py").unlink()
