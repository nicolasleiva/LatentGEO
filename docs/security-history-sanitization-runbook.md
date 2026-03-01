# Git History Sanitization Runbook

## Goal

Create and validate a sanitized history branch (`sanitized/main`) before any cutover on `main`.

## Preconditions

1. Freeze merge activity for the sanitization window.
2. Confirm all leaked credentials are already rotated/revoked.
3. Ensure a fresh mirror clone is available.

## Procedure

1. Create a mirror clone:
   ```bash
   git clone --mirror https://github.com/nicolasleiva/LatentGEO.git latentgeo-sanitized.git
   cd latentgeo-sanitized.git
   ```
2. Prepare replacement rules (`replacements.txt`):
   - `regex:sk-[A-Za-z0-9_-]{20,}==>sk-REDACTED`
   - `regex:AIza[0-9A-Za-z_-]{20,}==>AIzaREDACTED`
   - `regex:(password\\s*=\\s*[\"']).+?([\"'])==>password=\\1REDACTED\\2`
3. Run history rewrite:
   ```bash
   git filter-repo --replace-text replacements.txt --force
   ```
4. Verify no leaked tokens remain:
   ```bash
   git log -p | grep -E "sk-|AIza" || true
   ```
5. Push sanitized history to staging branch:
   ```bash
   git push origin --force --all
   git push origin HEAD:refs/heads/sanitized/main --force
   ```
6. Run CI and secret scanning on `sanitized/main`.

## Validation Gates

1. `detect-secrets` passes against `.secrets.baseline`.
2. TruffleHog returns no verified leaks.
3. Security workflows on GitHub complete successfully.

## Cutover Plan (post-approval)

1. Temporarily lock `main`.
2. Force-update `main` from `sanitized/main`.
3. Publish re-clone/rebase instructions to all contributors.
4. Re-enable protections and required checks.
