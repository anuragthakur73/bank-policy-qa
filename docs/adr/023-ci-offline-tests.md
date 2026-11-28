# ADR-023: CI on every push: complete lock file, Python 3.12, tests that cannot touch the network

Date: 29 Nov 2026 · Status: accepted (Week 7 S1)

Numbering: ADR-022 is reserved for the `/v1` additions for Project 1B (Week 7 S2).

## Context
Until Week 7 the tests ran only on Anurag's Windows PC. Project 1B will depend on 1A's `/v1` API, so a change
in 1A that breaks a test must be visible on GitHub, on every push. Week 6 found that `pip install -r
requirements.txt` failed on Linux with Python 3.10.

What reproducing it on Linux showed (29 Nov):
1. `altair==6.3.0` requires Python >= 3.11. On 3.12 the file installs on Linux; the problem was the Python
   version, not the platform.
2. The file was not a complete lock: 100 packages (plus the spaCy model) were pinned but 138 were installed. 38 were left
   to float, among them spaCy, thinc, aiohttp, SQLAlchemy and tldextract. A new spaCy release could have broken name
   masking (en_core_web_lg 3.8.0 needs spaCy 3.8.x) with no change in this repo.
3. **The masking step made a network call.** Presidio's email recogniser checks the domain with tldextract, whose
   default downloads the Public Suffix List from publicsuffix.org the first time it runs on a machine. On Anurag's
   PC the downloaded copy was already cached, so no test noticed. With sockets blocked on a fresh machine, three
   masking tests failed. In a bank, where outbound internet is usually restricted, the first email in a question
   would have waited for a connection that is never allowed.

## Options (for the network check)
| Option | Effect | Chosen |
|---|---|---|
| Trust that the tests are offline (no API keys in CI) | Misses calls that need no key, like finding 3 | No |
| Point proxy variables at a dead port | Only blocks libraries that honour proxy settings | No |
| `pytest-socket` (`--disable-socket --allow-unix-socket`) | Any test opening an internet socket fails, naming the call | **Yes** |

## Decision
1. `requirements.txt` is a complete lock: all 139 packages pinned (`pip freeze --all --exclude pip` on Python
   3.12), plus the spaCy model wheel. No existing pin changed. Adds `pytest-socket==0.8.1`.
2. `.github/workflows/ci.yml`: Ubuntu 24.04, Python 3.12, on every push and pull request. The whole virtualenv,
   including the ~425 MB spaCy model, is cached with a key made of the exact Python version and the hash of
   `requirements.txt`, so a cache hit downloads nothing and any change to the lock rebuilds it. A step loads
   en_core_web_lg before the tests, so a missing model fails with a clear message (ADR-021 masking fails closed).
   API keys are set to empty strings. `permissions: contents: read`.
3. Tests run with `--disable-socket --allow-unix-socket`. The 5 parser tests skip in CI because `data/raw` (RBI
   pages) is not redistributed; the skip reasons are printed (`-rs`).
4. `app/pii.py` gives Presidio's email check a tldextract that uses the suffix list bundled with the package
   (`suffix_list_urls=()`, no cache folder). New test `test_email_masking_needs_no_network` runs masking in a
   fresh process with an empty home folder and sockets blocked; it fails without the fix.

## Consequences
- CI time: about 11 s of tests; the first run (cache miss) also installs 139 packages and the model.
- The bundled suffix list is as old as the pinned tldextract (5.4.0). For checking that an email domain looks
  valid that is enough; a new top-level domain added after that release could be missed. Masking is the goal,
  not domain validation, and upgrading tldextract refreshes the list.
- Upgrading any package now means editing the lock, a fresh 3.12 install and a green CI run.
- Not in CI yet: gitleaks (runs as a Windows pre-commit hook only), live eval (needs keys and costs money), lint.
