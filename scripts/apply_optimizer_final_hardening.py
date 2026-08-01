from pathlib import Path


def replace_once(path, old, new):
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


worker_path = Path("public/optimizer-worker.js")
worker = worker_path.read_text(encoding="utf-8")
start = worker.index("function selectDeepMasks({")
end = worker.index("\nfunction buildSubsetSums", start)
replacement = r'''function searchBudgetPlan(primaryObjective, searchBudget) {
  const primaryQuota = Math.floor(searchBudget * 0.50);
  const secondaryQuota = Math.floor(searchBudget * 0.10);
  const requested = Object.fromEntries(
    OBJECTIVES.map((objective) => [
      objective,
      objective === primaryObjective ? primaryQuota : secondaryQuota,
    ]),
  );
  requested.pareto_diversity = (
    searchBudget
    - primaryQuota
    - secondaryQuota * (OBJECTIVES.length - 1)
  );
  return requested;
}

function selectDeepMasks({
  records,
  indexByMask,
  primaryObjective,
  searchBudget,
  seedText,
}) {
  const rankings = Object.fromEntries(
    OBJECTIVES.map((objective) => [objective, sortedIndexes(records, objective)]),
  );
  const selected = new Set();
  const trace = [];
  const random = xorshift32(hashSeed(seedText));
  const requested = searchBudgetPlan(primaryObjective, searchBudget);
  const actual = Object.fromEntries(
    [...OBJECTIVES, "pareto_diversity"].map((key) => [key, 0]),
  );
  const objectiveOrder = [
    primaryObjective,
    ...OBJECTIVES.filter((objective) => objective !== primaryObjective),
  ];

  for (const objective of objectiveOrder) {
    const ranking = rankings[objective];
    const localCandidates = new Set();
    const seedCount = objective === primaryObjective ? 80 : 30;
    for (let seed = 0; seed < seedCount; seed += 1) {
      const seedIndex = ranking[seed];
      localCandidates.add(records[seedIndex].mask);
      hillClimb({
        seedIndex,
        objective,
        records,
        indexByMask,
        selected: localCandidates,
        trace,
        random,
      });
    }

    const addForObjective = (mask) => {
      if (actual[objective] >= requested[objective] || selected.has(mask)) return;
      selected.add(mask);
      actual[objective] += 1;
    };
    for (const mask of localCandidates) addForObjective(mask);
    for (const recordIndex of ranking) {
      addForObjective(records[recordIndex].mask);
      if (actual[objective] >= requested[objective]) break;
    }
    if (actual[objective] !== requested[objective]) {
      throw new Error(
        `無法滿足 ${objective} 搜尋配額：${actual[objective]} / ${requested[objective]}`,
      );
    }
  }

  const masks = records.map((record) => record.mask);
  const anchors = OBJECTIVES.flatMap(
    (objective) => rankings[objective].slice(0, 5).map((index) => records[index].mask),
  );
  const diversityStart = selected.size;
  addDiversity({
    selected,
    masks,
    target: diversityStart + requested.pareto_diversity,
    random,
    anchors,
  });
  if (selected.size < searchBudget) {
    for (const mask of masks) {
      selected.add(mask);
      if (selected.size >= searchBudget) break;
    }
  }
  actual.pareto_diversity = selected.size - diversityStart;
  if (
    selected.size !== searchBudget
    || actual.pareto_diversity !== requested.pareto_diversity
  ) {
    throw new Error(
      `無法滿足 Pareto／多樣性配額：${actual.pareto_diversity} / ${requested.pareto_diversity}`,
    );
  }

  return {
    masks: Uint32Array.from(selected),
    trace,
    allocation: { requested, actual },
  };
}
'''
worker = worker[:start] + replacement + worker[end:]
old_digest = r'''async function digestMasks(masks) {
  const bytes = new Uint8Array(masks.buffer, masks.byteOffset, masks.byteLength);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}'''
new_digest = r'''export function serializeMasksLittleEndian(masks) {
  const bytes = new Uint8Array(masks.length * 4);
  const view = new DataView(bytes.buffer);
  for (let index = 0; index < masks.length; index += 1) {
    view.setUint32(index * 4, masks[index], true);
  }
  return bytes;
}

async function digestMasks(masks) {
  const bytes = serializeMasksLittleEndian(masks);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}'''
if worker.count(old_digest) != 1:
    raise SystemExit(f"optimizer digest matches={worker.count(old_digest)}")
worker_path.write_text(worker.replace(old_digest, new_digest, 1), encoding="utf-8")

replace_once(
    "worker/index.js",
    "const OPTIMIZER_MAX_REQUEST_BYTES = 2 * 1024 * 1024;",
    "const OPTIMIZER_MAX_REQUEST_BYTES = 3 * 1024 * 1024;",
)

proxy_test = Path("tests/test_optimizer_worker_proxy.mjs")
proxy = proxy_test.read_text(encoding="utf-8")
proxy = proxy.replace(
    'test("optimizer payloads above 2 MiB fail closed", async () => {',
    'test("optimizer payloads above 3 MiB fail closed", async () => {',
    1,
).replace(
    'body: JSON.stringify({ value: "x".repeat(2 * 1024 * 1024 + 1024) }),',
    'body: JSON.stringify({ value: "x".repeat(3 * 1024 * 1024 + 1024) }),',
    1,
)
proxy_test.write_text(proxy, encoding="utf-8")

worker_test = Path("tests/test_optimizer_worker.mjs")
test_text = worker_test.read_text(encoding="utf-8")
test_text = test_text.replace(
    "  relativeBandBounds,\n} from \"../public/optimizer-worker.js\";",
    "  relativeBandBounds,\n  serializeMasksLittleEndian,\n} from \"../public/optimizer-worker.js\";",
    1,
)
test_text = test_text.replace(
    '''test("relative band uses target-weight percentage", () => {
  const bounds = relativeBandBounds(0.10, 0.20);
  assert.ok(Math.abs(bounds.lower - 0.08) < 1e-12);
  assert.ok(Math.abs(bounds.upper - 0.12) < 1e-12);
});
''',
    '''test("relative band uses target-weight percentage", () => {
  const bounds = relativeBandBounds(0.10, 0.20);
  assert.ok(Math.abs(bounds.lower - 0.08) < 1e-12);
  assert.ok(Math.abs(bounds.upper - 0.12) < 1e-12);
});


test("mask audit bytes use explicit little-endian uint32 encoding", () => {
  const bytes = serializeMasksLittleEndian(Uint32Array.from([0x01020304, 0xa0b0c0d0]));
  assert.deepEqual(
    [...bytes],
    [0x04, 0x03, 0x02, 0x01, 0xd0, 0xc0, 0xb0, 0xa0],
  );
});
''',
    1,
)
test_text = test_text.replace(
    '''  assert.equal(result.search.evaluatedMaskHash.length, 64);
  assert.equal(result.combinations.length, 300);''',
    '''  assert.equal(result.search.evaluatedMaskHash.length, 64);
  assert.deepEqual(result.search.budgetAllocation, {
    requested: {
      sortino_ratio: 500,
      cagr: 100,
      mdd_abs: 100,
      beta_abs: 100,
      alpha: 100,
      pareto_diversity: 100,
    },
    actual: {
      sortino_ratio: 500,
      cagr: 100,
      mdd_abs: 100,
      beta_abs: 100,
      alpha: 100,
      pareto_diversity: 100,
    },
  });
  assert.equal(result.combinations.length, 300);''',
    1,
)
worker_test.write_text(test_text, encoding="utf-8")

for path in ("docs/PORTFOLIO_OPTIMIZER_MVP.md", "docs/OPTIMIZER_IMPLEMENTATION_STATUS.md"):
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if path.endswith("PORTFOLIO_OPTIMIZER_MVP.md"):
        text += '''\n## 最終工程邊界\n\n- 30,000 組實際唯一貢獻必須等於：主要目標 15,000、其餘四目標各 3,000、Pareto／多樣性 3,000。輸出同時保存 requested 與 actual；不允許只報名義配額。\n- 搜尋 bitmask 雜湊固定使用 little-endian unsigned 32-bit 序列，不依賴瀏覽器或 CPU 原生位元組序。\n- 後端壓縮快照上限 2 MiB；Base64 膨脹與 300 組複驗設定納入後，Cloudflare optimizer 專用請求上限為 3 MiB。普通 API 仍為 256 KiB。\n'''
    else:
        text += '''\nFinal hardening guarantees exact unique budget contributions, explicit little-endian mask hashing, and a 3 MiB optimizer-only edge request ceiling compatible with the 2 MiB compressed snapshot ceiling.\n'''
    file.write_text(text, encoding="utf-8")

Path("scripts/apply_optimizer_final_hardening.py").unlink()
