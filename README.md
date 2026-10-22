# findme

> **Status: DRAFT assessment, not finished.** See "TODO / to be finished" below.

## What this seems to be

A small "where did I write that?" tool. It walks a directory tree (the whole filesystem, `/`,
in the original), picks files with a given extension (`.py`), and prints the full contents of
every file that contains a search phrase (hardcoded to `portfolio`). Files with identical content
(same SHA-256) are only shown once, so the many copies of the same script lying around in
backups, clones and virtualenvs don't flood the output. At the end it prints how many files were
searched and how many matched.

In short: a dedup-aware, content-dumping `grep -rl` for finding a lost script/snippet on your own
machine.

## Current state

What works:

- Walking the tree with `os.walk`, filtering by a single extension and skipping empty files.
- Substring search line by line; files that fail to decode as text are silently skipped.
- SHA-256 deduplication of matching files (via `mmap`).
- Prints a banner + full file content for each unique match, and a summary.

What is broken / missing:

- Everything is hardcoded in `main()`: root `/`, extension `py`, phrase `portfolio`, and an
  exclusion list tuned to one machine (`pycharm`, `python-skeletons`, `flatpak`, `/usr/lib/python`).
- No CLI at all; you edit the source to change the search.
- Exclusions are plain substring matches on the full path, so `cache` also excludes e.g.
  `/home/me/projects/cachetools/`.
- `PermissionError` (very common when walking `/`) and other `OSError`s while reading crash it.
- Duplicates are detected but not reported (only "Skipping, same file was already processed."),
  so you can't tell where the other copies live.
- Only one extension; matching is case-sensitive only; no regex; always dumps the whole file.
- `compute_hash_plain`, the `defaultdict(list)` path lists, and `is_current` are half-used.
- No packaging, no tests.

No secrets or personal data were committed; the exclusion list just reflects the author's machine.

## TODO / to be finished

- [ ] Redesign as a package with a real CLI (root, extensions, phrase, excludes, options).
- [ ] Separate pure logic (filtering, matching, dedup grouping) from filesystem I/O.
- [ ] Usage docs, tests.
