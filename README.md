# BacktestStock

> **FROZEN — NO ACTIVE DEVELOPMENT**
>
> BacktestStock 已於 2026-08-19 進入功能凍結狀態。專案保留目前 production 使用者功能與必要資料/安全/復原契約，不再進行功能擴充、非必要 refactor、framework migration 或方法論擴張。

## 使用者功能

目前凍結的 production 功能包括：

- 多市場 TWD 投資組合回測
- Universe / Scanner 與基本面預篩選
- Exhaustive historical search / portfolio optimizer
- Portfolio v3
- Portfolio Refinery
- Walk-Forward Research
- Optimizer Hub
- ResearchRun / Research Library

## Production 架構

```text
Browser
  -> Cloudflare Worker + static assets
     -> Cloudflare D1 (Universe / PIT / ResearchRun)
     -> Vercel Functions
        -> apps/api/app/ quantitative/data/research authorities
```

Production backend origin：`https://stockbacktest.vercel.app`

主要 runtime 目錄：

```text
api/             Vercel production entrypoints / compatibility runtime
apps/api/app/    data / portfolio / research / quant / refinery runtime
migrations/      D1 schema reconstruction history
public/          frozen production browser assets
scripts/         runtime-imported code only
worker/          Cloudflare production runtime + Universe scheduler
```

## 凍結原則

- TWD canonical valuation、quantitative semantics、Portfolio v3、PIT / Walk-Forward causality 與 ResearchRun authorities 保持目前 production 行為。
- API / Worker / storage compatibility 不因「清理」而重構。
- Browser saved state 與現有 localStorage compatibility 不主動破壞。
- D1 Universe version history、PIT evidence、ResearchRun records 屬產品資料，不是開發垃圾。
- Production runtime 所需的 legacy-looking module 若仍被 import，繼續保留。

## 必要營運依賴

Universe membership 由 Cloudflare Worker Cron 直接取得四個既有來源、執行 freshness / member-count / churn / checksum fail-closed 驗證後發布到 D1。正式排程為每週一、四 `06:17 UTC`。

2026-08-19 production acceptance 已實際證明 Cloudflare Cron 可自主刷新全部四個 Universe；GitHub scheduled updater 已退出 production authority。

## Recovery

Pre-sunset exact recovery point：

- commit: `ede589c289103089fa77e1a9eb5a24ed882d62ea`
- branch: `release-backup/pre-sunset-runtime-20260819`

完整開發文件、測試、舊分支與歷史設計仍可由 Git history / PR / Issue history 或上述 recovery point 還原；它們不再保留在 Frozen Runtime active tree。

若未來重新啟動開發，應先從 recovery point / Git history 重建開發工具與驗證環境，再變更 production runtime。
