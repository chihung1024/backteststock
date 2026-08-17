from pathlib import Path

path = Path("to_do_update_list.md")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        """Status: **4A-7A RELIABILITY + 4A-7B PRODUCT UX INTERNALLY VERIFIED / FORMAL PR GATES NEXT**.\n\n```text\ninternal-4a7-research-memory-finalize@93c85c5c5de46384b1c1078345638cd5aaf1dc92\nInternal Research Library Product Verify #3\nrun 31998851073: SUCCESS\n```""",
        """Status: **4A-7A RELIABILITY + 4A-7B PRODUCT UX INTERNALLY VERIFIED / PR #165 EXACT-HEAD GATES NEXT**.\n\n```text\nDraft PR #165: feat/4a7-research-memory\nfinal internal source: internal-4a7-context-boundary@717bdf46b7fa951fd39ffb00935c473a85d6ae9d\nInternal 4A-7 Context Boundary #3\nrun 31999833266: SUCCESS\n```""",
    ),
    (
        """5. Exact-PR self-review found the initial 4 MiB result guard exceeded Cloudflare D1's 2,000,000-byte string/row limit. Root fix budgets the full request plus a 64 KiB row reserve and rejects oversized completed evidence with 413 before any D1 write.\n""",
        """5. Exact-PR self-review found the initial 4 MiB result guard exceeded Cloudflare D1's 2,000,000-byte string/row limit. Root fix budgets the full request plus a 64 KiB row reserve and rejects oversized completed evidence with 413 before any D1 write.\n6. ResearchRun's trusted synthetic Walk-Forward request initially lost Cloudflare client identity. The existing backend 2/minute rate limiter could therefore collapse unrelated users onto a shared Worker/serverless egress bucket. Root fix propagates only trusted `cf-connecting-ip` into the synthetic request so the existing proxy emits per-client `x-forwarded-for`; browser authorization/cookie/recovery credentials remain stripped.\n7. Capability auto-refresh, manual refresh and recovery-code connect originally relied on AbortController without the same operation-generation authority used by save/rerun. If a transport ignored AbortSignal, a late response could refill stale library state or persist an obsolete recovery code after workspace unmount. Root fix applies `operationVersion` + active-controller identity to these paths and adds a late-connect/unmount browser regression.\n""",
    ),
    (
        """Exact internal gate `31998851073` SUCCESS:\n- clean `npm ci`;\n- JavaScript + score regressions;\n- Worker authority/security 118 / 118 PASS;\n- D1 migrations 0001 → 0005 from empty state + ResearchRun schema checks;\n- Portfolio TypeScript + production Vite build;\n- Cloudflare Wrangler dry-run;\n- 15 targeted Walk-Forward/Research Library browser cases including mobile, concurrency and stale-response race;\n- temporary product verifier/scripts removed from final tree.""",
        """Final hardening gate `31999833266` SUCCESS:\n- clean `npm ci`;\n- JavaScript checks;\n- Worker authority/security **120 / 120 PASS**, including D1 row-bound rejection and trusted per-client limiter identity without browser credential forwarding;\n- Portfolio TypeScript + production Vite build;\n- Cloudflare Wrangler dry-run;\n- **15 / 15 targeted browser PASS**, including save cancellation, late-connect/unmount credential race, admission, rate-limit UX, history/detail/rerun/recovery, concurrency and 390px mobile containment;\n- temporary context verifier/script removed from the final tree.\n\nSchema remained unchanged during the final context hardening. Earlier exact-candidate verification `31998851073` already rehearsed D1 migrations 0001 → 0005 from an empty local state and confirmed both ResearchRun tables.""",
    ),
    (
        """`formal feat/4a7-research-memory → Draft PR → exact-head CI + intended Vercel Preview → independent R3 exact-head review → merge only with no BLOCKER and green required gates`.""",
        """`fast-forward feat/4a7-research-memory to the verified final source → exact-head CI + intended Vercel Preview → mark PR #165 Ready → independent cchung911 R3 exact-head review → merge only with no BLOCKER and green required gates`.""",
    ),
]

for before, after in replacements:
    count = text.count(before)
    if count != 1:
        raise SystemExit(f"handoff anchor mismatch ({count}): {before[:120]!r}")
    text = text.replace(before, after, 1)

path.write_text(text, encoding="utf-8")
