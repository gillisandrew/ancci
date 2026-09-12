# Repositories

There is no repository acquirer, on purpose. Cloning a repository and reading its files is
something you already do well, and a fetcher wrapping it would only add guesses about where
the documentation lives and how much of it to take.

## Read it directly

```bash
git clone --depth 1 --filter=blob:none https://github.com/<owner>/<name> /tmp/<name>
```

Then read what is actually there. Documentation usually sits in `docs/`, sometimes in
`site/`, `handbook/` or `website/docs/`, and the README is often the best single page. Look
before assuming — `mkdocs.yml`, `docusaurus.config.*` or `conf.py` name the docs directory
outright when they exist.

Take the parts that suit the deck rather than everything. A research note distilled from
four relevant pages beats one distilled from an entire documentation set.

## Pin the commit you read

A branch moves; what you read does not. Record the exact commit:

```bash
git -C /tmp/<name> rev-parse HEAD
```

Then cite it, naming the file a fact came from:

```yaml
sources:
  - type: repo
    repo: anthropics/claude-code
    ref: 9fab82e1c0d4...
    path: docs/hooks.md
```

This matters more than it looks: "main" in six months is not the thing you read, and a card
whose citation cannot be checked is a card nobody can fix later.

## A single file is just a page

To read one rendered file rather than clone, pass its URL to `add-source.py` — a GitHub URL
is fetched as an ordinary web page, which for a repository root gives you the rendered
README.
