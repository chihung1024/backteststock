# Unified API migration core

This directory is the framework-neutral core for the staged replacement of the
current `api/` Flask runtime.  It is intentionally not a separate Vercel
entrypoint yet; the current Flask compatibility routes call its services while
the eventual FastAPI cutover is compared and validated.

The first invariant is implemented in `app/data/twd_valuation.py`:

```text
TWD adjusted close = native adjusted close × (TWD per native currency unit)
```

The calendar is the union of the native market and FX market calendars.  Native
prices and FX rates may be carried forward only after a previously observed
value; backward filling from a later FX quote is forbidden.  This keeps an
FX-only day visible in every TWD return path and prevents future-data leakage.

`api/index_v2.py`, `api/scan_v2.py`, and `api/exhaustive_optimizer.py` now use
this core for TWD portfolio, scan, and exhaustive-snapshot paths.  The separate
FastAPI process is deliberately deferred, not the TWD calculation contract.
