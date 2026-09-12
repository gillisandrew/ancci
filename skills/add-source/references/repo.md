# GitHub repositories

Accepts `owner/name` or a repository URL. A URL pointing *inside* a repository — a blob, a
file, a pull request — is treated as a web page instead, which is usually what you want.

## What actually gets downloaded

A partial clone (`--filter=blob:none`) with a sparse checkout, so blobs arrive only for the
paths worth reading. On a large repository this is a few megabytes rather than tens.

Collected, in this order:

- Root files: `README`, `CONTRIBUTING`, `ARCHITECTURE`, `CHANGELOG`
- `docs/`, `doc/`, `documentation/`, `guide/`, `guides/`, `website/docs/`
- Only `.md`, `.markdown`, `.mdx`, `.rst`, `.txt`

Each file appears under a `## <path>` heading, so you always know which file a fact came
from. Collection stops at roughly 400,000 characters — for a big documentation set you are
reading a prefix, not the whole thing. Say so in the note if it was truncated.

**Source code is not collected.** This reads documentation. If a card needs to be about
actual implementation, fetch the specific file as a web page instead.

## Pin the commit

The ref is resolved to a full commit sha before anything is read, and that sha is what gets
cited:

```yaml
sources:
  - type: repo
    repo: anthropics/claude-code
    ref: 9fab82e1c0...
    path: docs/hooks.md
```

Add `path` yourself when a fact came from one file — the fetch records the repository and
the commit, and you know which file you read it in.

Use `--ref` to read a tag or an older commit. Without it you get the default branch as it
is right now, which is the correct default and also the reason the sha matters: "main" in
six months is not the thing you read.

## When it fails

A private or missing repository fails at `ls-remote`. A repository with no documentation
directories reports that it found none — worth checking whether the docs live somewhere
unusual (`site/`, `handbook/`) and fetching those pages directly instead.
