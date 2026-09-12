"""Reading a GitHub repository's documentation.

Cloning a whole repository to read its docs wastes most of the download. A partial clone
with a sparse checkout fetches the documentation and the root files and nothing else, which
on a large repository is a few megabytes rather than tens.

Shells out to git deliberately: git is already installed, already knows the user's
credentials and proxies, and is not going to break on its own schedule.
"""

import re
import subprocess
from pathlib import Path

from ..sources import RepoSource
from .types import Fetched, FetchError

# Where documentation lives, in rough order of how likely it is to be the real thing.
DOC_DIRS = ("docs", "doc", "documentation", "guide", "guides", "website/docs")
ROOT_FILES = ("README.md", "README.rst", "CONTRIBUTING.md", "ARCHITECTURE.md", "CHANGELOG.md")
TEXT_SUFFIXES = {".md", ".markdown", ".mdx", ".rst", ".txt"}

_SLUG = re.compile(r"^[\w.-]+/[\w.-]+$")


def parse_repo(spec: str) -> str:
    """`owner/name`, or any github.com URL pointing at one."""
    spec = spec.strip().removesuffix(".git")
    if _SLUG.match(spec):
        return spec
    match = re.search(r"github\.com[:/]+([\w.-]+/[\w.-]+)", spec)
    if not match:
        raise FetchError(f"not a GitHub repository: {spec}")
    return match.group(1)


def _git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        raise FetchError(f"git {' '.join(args[:2])} failed: {result.stderr.strip().splitlines()[-1:] or ['?']}")
    return result.stdout


def resolve_ref(repo: str, ref: str | None) -> str:
    """Pin what was actually read. A branch name moves; a commit does not."""
    target = ref or "HEAD"
    out = _git("ls-remote", f"https://github.com/{repo}.git", target)
    if not out.strip():
        raise FetchError(f"no such ref {target!r} in {repo}")
    return out.split()[0]


def clone_docs(repo: str, sha: str, into: Path) -> Path:
    """Partial + sparse clone: blobs on demand, and only the paths worth reading.

    Cone mode brings the root files along with the docs directories, which is exactly the
    corpus worth reading and very little else.
    """
    if into.exists():
        return into
    into.parent.mkdir(parents=True, exist_ok=True)
    _git(
        "clone", "--quiet", "--filter=blob:none", "--sparse", "--no-checkout",
        f"https://github.com/{repo}.git", str(into),
    )
    _git("sparse-checkout", "set", "--cone", *DOC_DIRS, cwd=into)
    _git("checkout", "--quiet", sha, cwd=into)
    return into


def collect(root: Path, limit: int = 400_000) -> tuple[str, list[str]]:
    """Concatenate the readable documentation, each file under a heading naming its path."""
    seen: list[Path] = []
    for name in ROOT_FILES:
        if (root / name).is_file():
            seen.append(root / name)
    for directory in DOC_DIRS:
        base = root / directory
        if base.is_dir():
            seen += sorted(p for p in base.rglob("*") if p.suffix.lower() in TEXT_SUFFIXES)

    parts, used, total = [], [], 0
    for path in seen:
        try:
            body = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if not body:
            continue
        rel = path.relative_to(root).as_posix()
        chunk = f"\n\n## {rel}\n\n{body}"
        if total + len(chunk) > limit:
            break
        parts.append(chunk)
        used.append(rel)
        total += len(chunk)
    if not parts:
        raise FetchError(f"no documentation found in {root.name}; looked in {', '.join(DOC_DIRS)}")
    return "".join(parts).strip(), used


def fetch(spec: str, cache: Path, ref: str | None = None) -> Fetched:
    repo = parse_repo(spec)
    sha = resolve_ref(repo, ref)
    checkout = clone_docs(repo, sha, cache / "repos" / f"{repo.replace('/', '_')}@{sha[:12]}")
    text, files = collect(checkout)
    return Fetched(
        text=f"# {repo} @ {sha[:7]}\n{text}",
        citation=RepoSource(repo=repo, ref=sha),
        title=repo.replace("/", " "),
        notes={"files": ", ".join(files[:20]), "file_count": str(len(files))},
    )
