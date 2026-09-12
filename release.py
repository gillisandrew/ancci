#!/usr/bin/env -S uv run --script --no-config
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Cut a release: bump both manifests, verify, commit, tag, push.

The version lives in two files, and until now nothing checked that they agreed. Bumping by
hand had two ways to fail — forgetting entirely, which shipped three feature releases that
nobody received, and changing one file but not the other. This owns both.

    ./release.py 0.4.0
    ./release.py 0.4.0 --dry-run

Writes with a targeted replacement rather than re-serialising the JSON, so comments,
spacing and key order survive untouched.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _parts(version: str) -> tuple[int, ...]:
    """Compare as numbers. As strings, 0.10.0 sorts below 0.9.0."""
    return tuple(int(part) for part in SEMVER.match(version).groups())


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and result.returncode != 0:
        fail(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def shell(label: str, *args: str) -> None:
    print(f"  {label}…", end=" ", flush=True)
    # This script runs in a uv environment of its own. Leaking VIRTUAL_ENV into the
    # project's tooling makes uv warn on every release about an env it then ignores.
    env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        print("failed")
        print((result.stdout + result.stderr).strip()[-1500:], file=sys.stderr)
        revert()
        fail(f"{label} failed; the version bump has been reverted")
    print("ok")


def revert() -> None:
    git("checkout", "--", str(PLUGIN.relative_to(ROOT)), str(MARKETPLACE.relative_to(ROOT)), check=False)


def versions() -> tuple[str, str, str]:
    """The plugin's name, its version, and the version its marketplace entry claims."""
    plugin = json.loads(PLUGIN.read_text())
    entries = json.loads(MARKETPLACE.read_text()).get("plugins", [])
    entry = next((e for e in entries if e.get("name") == plugin["name"]), None)
    if entry is None:
        fail(f"{MARKETPLACE.name} has no entry named {plugin['name']!r}")
    return plugin["name"], plugin.get("version", ""), entry.get("version", "")


def bump(path: Path, old: str, new: str) -> None:
    """Replace the one version string, leaving every other byte of the file alone."""
    text = path.read_text()
    needle = f'"version": "{old}"'
    found = text.count(needle)
    if found != 1:
        fail(f"{path.name}: expected exactly one {needle}, found {found}")
    path.write_text(text.replace(needle, f'"version": "{new}"'))


def main() -> int:
    parser = argparse.ArgumentParser(prog="release.py", description=__doc__)
    parser.add_argument("version", help="the version to release, e.g. 0.4.0")
    parser.add_argument("--dry-run", action="store_true", help="say what would happen and stop")
    parser.add_argument("--no-push", action="store_true", help="commit and tag, but do not push")
    args = parser.parse_args()

    if not SEMVER.match(args.version):
        fail(f"{args.version!r} is not MAJOR.MINOR.PATCH")

    name, plugin_version, market_version = versions()
    if plugin_version != market_version:
        fail(
            f"the manifests already disagree: plugin.json {plugin_version!r}, "
            f"marketplace.json {market_version!r}. Fix that first."
        )
    if not SEMVER.match(plugin_version):
        fail(f"the current version {plugin_version!r} is not MAJOR.MINOR.PATCH; fix that first")
    if _parts(args.version) <= _parts(plugin_version):
        fail(f"{args.version} is not newer than the current {plugin_version}")

    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    dirty = git("status", "--porcelain")
    if dirty:
        fail("the working tree is dirty; a release should not sweep up unrelated changes:\n" + dirty)
    if git("tag", "-l", f"v{args.version}"):
        fail(f"tag v{args.version} already exists")

    print(f"{name}: {plugin_version} -> {args.version} on {branch}")
    if args.dry_run:
        print("  dry run: nothing written")
        return 0

    bump(PLUGIN, plugin_version, args.version)
    bump(MARKETPLACE, plugin_version, args.version)
    print(f"  bumped both manifests to {args.version}")

    shell("validate", "claude", "plugin", "validate", ".", "--strict")
    shell("tests", "uv", "run", "pytest", "-q")

    git("add", "--", ".claude-plugin")
    git("commit", "-q", "-m", f"Release {args.version}")
    git("tag", "-a", f"v{args.version}", "-m", f"Release {args.version}")
    print(f"  committed and tagged v{args.version}")

    if args.no_push:
        print(f"  not pushed. When ready: git push origin {branch} --follow-tags")
        return 0
    git("push", "--quiet", "--follow-tags", "origin", branch)
    print(f"  pushed to origin/{branch}")
    print(f"\n{name} {args.version} is live. Installed copies pick it up with /plugin update {name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
