# ADR-024: A CI job here that fails when Project 1B's saved rules no longer match this repo

Date: 29 Nov 2026 · Status: accepted (Week 8 S2) · Related: ADR-022 (`/v1/rules`), loan-precheck ADR-002 (S2 addendum)

## Context
Project 1B (`loan-precheck`) checks loan files with code against the rules in force, read from `GET /v1/rules`. Its
tests and CI run offline on saved copies (`loan-precheck/rules_snapshot/`). 1B's `scripts.snapshot_rules --check`
finds drift, but only when someone runs it on the PC with this API up; 1B's CI cannot start this repo.
The failure it guards against was shown on 29 Nov: DB-HL-011's FOIR band changed here from 55% to 58% without a
snapshot refresh, and 1B's live golden run reported F12 as "Eligible – Deviation Approval Required" instead of
"Not Eligible". A policy edit is made in *this* repo, so this repo is where the alarm belongs.

## Options
| Option | Catches a policy edit here | Catches a hand edit in 1B | Cost | Chosen |
|---|---|---|---|---|
| Habit: refresh 1B in the same sitting | Only if remembered | No | none | Not enough alone |
| 1B CI starts 1A (checkout + install 1A, ~425 MB model) | On 1B pushes only | Yes | Heavy, couples 1B's CI to 1A's install | No |
| **Job here: check out 1B, compare its snapshots with this repo's `/v1/rules` in-process** | **On the commit that made it** | **Daily schedule** | Reuses this repo's cached venv | **Yes** |
| Copy 1B's comparison logic into this repo | Yes | Yes | Two definitions of "drift" to keep equal | No |

## Decision
1. `eval/check_1b_snapshots.py --precheck <loan-precheck checkout>`: serves this repo's API in-process (FastAPI
   `TestClient`: no server, no network, no model, no Qdrant) and calls **1B's own `check()`** from
   `scripts/snapshot_rules.py`, loaded by path (stdlib only). One definition of drift for both repos: a version
   added or gone, status or dates (approving a draft counts), a rule added or removed, any rule field at its exact
   path. Exit 0 no drift, 1 drift (listed, with the fix steps), 2 not a usable 1B checkout (missing, or older than
   Week 8 S2). Writes the result to the GitHub step summary.
2. `.github/workflows/1b-snapshots.yml` ("1B snapshots"): checks out this repo and `anuragthakur73/loan-precheck`
   `main` (public, read only, no credentials kept), restores the same venv cache as `ci.yml`, runs the check.
   Triggers: every push and pull request (a policy change goes red on its own commit or PR), daily at 08:47 IST
   (catches a change on 1B's side), and by hand (re-run after refreshing 1B). Separate from `ci.yml`, so a red
   "1B snapshots" means "refresh 1B", never "1A's tests broke".
3. The fix when it is red: start this API, in loan-precheck run `python -m scripts.snapshot_rules`, the tests and
   `python -m scripts.live_golden`, commit and push the snapshots, then re-run this workflow.

## Evidence (Claude's sandbox, 29 Nov, this repo's own lock file)
- Against loan-precheck 9e3d192 (fresh clone of `main`): **no drift**, 4 policy versions.
- DB-HL-011 band 2 edited here 0.55 → 0.58: exit 1, `home_loan v1.1.0 DB-HL-011: params.foir_bands[1].max_foir 0.55
  saved, 0.58 live`, and the same text in the step summary. Restored → exit 0.
- Not a 1B checkout → exit 2. `tests/test_check_1b_snapshots.py` (5): in-process API serves health and rules; a stub
  1B's `check()` is called with the in-process client and the right folder; drift → exit 1 + summary; missing or
  pre-S2 checkout → exit 2; the real comparison against `../loan-precheck` when that checkout exists (skipped in CI).
  Full suite 209 passed, 5 skipped (the parser tests, as before). `actionlint` clean on both workflows.

## Consequences and limits
- **Ordering:** a policy change here turns this job red until 1B's snapshots are refreshed and pushed; that is the
  point. Push the 1B refresh, then re-run this workflow (or wait for the daily run).
- The job trusts 1B's `main`. A change to 1B's `check()` changes what this job tests; it is reviewed in 1B.
- A 1B change is seen within a day, not on 1B's push (a cross-repo trigger needs a token; not worth it yet).
- It compares the saved copies, not 1B's results: a rule that changes but is not one 1B reads still goes red.
  Deliberate: the snapshots must equal the API; whether a change matters is for the live golden run to show.
