#!/usr/bin/env python3
"""_predeploy_check.py — gate before the manual production deploy (stdlib-only).

Production is published by hand from this directory:
    netlify deploy --prod --site=98c71b47-cb1e-4eb2-8255-963349df8ccf --dir=.
which ships whatever is on disk — including uncommitted edits — and gives git
no record of what went live. This gate makes that model safe:

    python _predeploy_check.py     # exit 0 = safe to deploy, exit 1 = fix first

PASS requires BOTH:
  1. clean working tree (no uncommitted or untracked changes), and
  2. HEAD == origin/main after a fresh fetch (so prod ships exactly what
     staging auto-deployed and tested).

If the fetch fails (offline), the check FAILS — deploying unverified against
the remote is the exact risk this script exists to block.
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent


def git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True)


def main():
    fails = []

    porcelain = git("status", "--porcelain")
    if porcelain.stdout.strip():
        fails.append("working tree not clean — commit or stash first:\n"
                     + "\n".join("      " + l for l in porcelain.stdout.strip().splitlines()))

    fetch = git("fetch", "origin", "main")
    if fetch.returncode != 0:
        fails.append("git fetch origin main failed (offline?): "
                     + (fetch.stderr.strip() or "unknown error"))
    else:
        head = git("rev-parse", "HEAD").stdout.strip()
        remote = git("rev-parse", "origin/main").stdout.strip()
        if head != remote:
            fails.append(f"HEAD ({head[:9]}) != origin/main ({remote[:9]}) — "
                         "push (or pull) so prod matches what staging tested")

    if fails:
        print("PREDEPLOY FAIL:")
        for f in fails:
            print("  - " + f)
        return 1

    head = git("rev-parse", "HEAD").stdout.strip()
    print(f"PREDEPLOY PASS — clean tree, HEAD {head[:9]} == origin/main. Safe to run:")
    print("  netlify deploy --prod --site=98c71b47-cb1e-4eb2-8255-963349df8ccf --dir=.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
