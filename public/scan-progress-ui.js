export function scanSettlementSnapshot(job) {
  const results = Array.isArray(job?.results) ? job.results : [];
  const total = Array.isArray(job?.payload?.tickers)
    ? job.payload.tickers.length
    : results.length;
  const successful = results.filter((item) => !item?.error && item?.retryable !== true).length;
  const failed = results.filter((item) => Boolean(item?.error)).length;
  const settled = results.length;
  return {
    settled,
    total,
    successful,
    failed,
    unfinished: Math.max(total - settled, 0),
  };
}

export function formatScanSettlement(snapshot, { includeUnfinished = false } = {}) {
  if (!snapshot || !Number.isSafeInteger(snapshot.total) || snapshot.total <= 0) return "";
  const parts = [
    `成功 ${snapshot.successful}`,
    `失敗 ${snapshot.failed}`,
  ];
  if (includeUnfinished) parts.push(`未完成 ${snapshot.unfinished}`);
  return `已結算 ${snapshot.settled} / ${snapshot.total} 檔（${parts.join("、")}）`;
}

function messageMatchesSnapshot(message, snapshot) {
  const match = String(message || "").match(/(\d+)\s*\/\s*(\d+)\s*檔/u);
  if (!match) return false;
  return Number(match[1]) === snapshot.settled && Number(match[2]) === snapshot.total;
}

export function rewriteScanProgressMessage(message, job) {
  const raw = String(message || "");
  if (!raw || raw.includes("已結算")) return raw;
  const snapshot = scanSettlementSnapshot(job);
  if (!messageMatchesSnapshot(raw, snapshot)) return raw;

  if (raw.startsWith("正在取得第 ")) {
    return `${raw.split("；")[0]}；${formatScanSettlement(snapshot)}`;
  }
  if (raw.startsWith("行情服務暫時未完整回應")) {
    return `行情服務暫時未完整回應；${formatScanSettlement(snapshot, { includeUnfinished: true })}，系統持續重試`;
  }
  if (raw.startsWith("上游暫時未完整回傳")) {
    return `${raw.split("；")[0]}；${formatScanSettlement(snapshot, { includeUnfinished: true })}`;
  }
  if (raw.startsWith("完整取得 ")) {
    return `回測結束：${formatScanSettlement(snapshot, { includeUnfinished: true })}`;
  }
  if (raw.startsWith("已還原 ")) {
    return `已還原進度：${formatScanSettlement(snapshot, { includeUnfinished: true })}`;
  }
  if (raw.startsWith("準備循序取得 ")) {
    return `準備掃描；${formatScanSettlement(snapshot, { includeUnfinished: true })}`;
  }
  if (raw.startsWith("已取得 ")) {
    return formatScanSettlement(snapshot, { includeUnfinished: true });
  }
  return raw;
}

export function rewriteScanStatusMessage(message, job) {
  const raw = String(message || "");
  if (!raw || raw.includes("已結算")) return raw;
  const snapshot = scanSettlementSnapshot(job);
  if (!messageMatchesSnapshot(raw, snapshot)) return raw;
  const settlement = formatScanSettlement(snapshot, { includeUnfinished: true });

  if (raw.startsWith("回測已暫停；已保存 ")) {
    const continuation = raw.includes("按「繼續未完成回測」")
      ? "，按「繼續未完成回測」即可接續。"
      : "。";
    return `回測已暫停；${settlement}${continuation}`;
  }
  if (raw.startsWith("進度已保存；系統可由目前的 ")) {
    return `進度已保存；${settlement}，系統可接續未完成回測。`;
  }
  return raw;
}
