# BacktestStock

> **FROZEN — NO ACTIVE DEVELOPMENT**
>
> BacktestStock 已於 2026-08-19 進入功能凍結狀態。專案只保留目前 production 使用者功能、必要資料更新、資料/安全正確性與重建契約；不再進行功能擴充、非必要 refactor、framework migration 或方法論擴張。

## 使用者功能

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

Frozen runtime 主要目錄：

```text
api/                 Vercel production entrypoints / compatibility runtime
apps/api/app/        data / portfolio / research / quant / refinery runtime
apps/portfolio-web/  Portfolio production browser source authority（維護/重建用途）
migrations/          D1 schema reconstruction history
public/              frozen production browser assets
scripts/             runtime-imported code only
worker/              Cloudflare production runtime + Universe scheduler
```

Active tree 仍維持功能凍結；只恢復 `apps/portfolio-web/` 作為目前 Portfolio production bundle 的可維護 source authority，避免直接修改 minified artifact。其他已退役的開發測試、部署 workflow、smoke tooling、backup branches 與暫存 artifacts 不因本次 production defect recovery 而恢復；歷史與重建資訊仍以 Git history / Release 為準。

## 凍結原則

- TWD canonical valuation、quantitative semantics、Portfolio v3、PIT / Walk-Forward causality 與 ResearchRun authorities 保持 production-accepted 行為。
- API / Worker / storage compatibility 不因清理而重構。
- Browser saved state 與既有 localStorage compatibility 不主動破壞。
- D1 Universe version history、PIT evidence、ResearchRun records 屬產品資料，不是開發垃圾。
- 名稱看似 legacy 但仍被 production import 的模組繼續保留。

## Universe 維運

Universe membership 由 Cloudflare Worker Cron 直接取得四個既有來源，執行 freshness、member-count、churn、checksum 等 fail-closed 驗證後發布至 D1。

正式排程：每週一、四 `06:17 UTC`。

2026-08-19 production acceptance 已實際證明 Cloudflare Cron 可自主刷新 S&P 500、NASDAQ-100、SOXX、Russell 2000 四個 Universe；GitHub scheduled updater 已退出 production authority。

## Recovery / Releases

完整開發環境與 production-accepted runtime 均已用 immutable Git tag / GitHub Release 保存：

- `archive/pre-sunset-2026-08-19`
  - commit `ede589c289103089fa77e1a9eb5a24ed882d62ea`
  - Sunset 前完整 recovery checkpoint；包含當時的開發文件、測試與部署工具。
- `runtime/accepted-2026-08-19`
  - commit `b90500b20ac1517dd49f63b33e22ab92c06e1d10`
  - Cloudflare Worker/D1、永久 Universe Cron、Vercel exact-SHA 與 production smoke 全部通過的 Frozen Runtime baseline。

Active repository 不再以 backup branch 保存歷史；歷史 PR / Issue / commit 與上述 Release/tag 是復原來源。

若未來重新啟動開發，應先從 `archive/pre-sunset-2026-08-19` 或 Git history 重建其餘開發工具與驗證環境，再變更 production runtime。