# findme

"Where did I write that?" Find the files under a directory that contain a phrase, show the
matching lines (or the whole file), and collapse byte-identical copies, so the same script
copied into five backups and clones shows up once, with a list of where the other copies live.

It started as a single script (`findme.py`, January 2024) that walked `/` looking for `.py`
files containing `portfolio`, printed each one in full and skipped files with a SHA-256 it had
already seen. This version keeps that idea and makes it a configurable command-line tool.

## Install

Requires Python 3.10+.

```console
$ python3 -m venv .venv
$ .venv/bin/pip install -e .          # or: pip install -e '.[dev]' for pytest
$ .venv/bin/findme --help
```

`python -m findme ...` works too.

## Usage

```
findme [options] PHRASE [ROOT ...]
```

`ROOT` defaults to `.`. Roots can be directories or single files.

| Option | Meaning |
| --- | --- |
| `-e, --ext EXT` | only files with this extension; repeatable or `py,md` (default: all files) |
| `-x, --exclude GLOB` | skip a name anywhere (`build`, `*.egg-info`) or a path (`/usr/lib`); repeatable |
| `--no-default-excludes` | also search `.git`, `.venv`, `node_modules`, `site-packages`, ... |
| `--max-size SIZE` | skip larger files (`512K`, `10M`, `0` = no limit; default `10M`) |
| `-L, --follow-symlinks` | follow symlinks (off by default, to avoid loops and double hits) |
| `-i, --ignore-case` | case-insensitive |
| `-r, --regex` | PHRASE is a Python regular expression (matched per line) |
| `--full` / `-l, --files-only` / `--json` | output mode (default: path + matching lines) |
| `-q, --quiet` / `-v, --verbose` | no summary on stderr / list every unreadable path |
| `--config FILE` / `--no-config` | use a specific config file / ignore the config file |

Exit status: `0` if something matched, `1` if nothing did, `2` on errors (bad regex, missing
root, bad config), like `grep`. Unreadable files are counted in the summary (list them with
`-v`) and don't change the exit status.

### Examples

These were run against a small sample tree: a `portfolio.py` in `projects/stocks/` with an
identical copy in `backup/old/`, a `README.md`, a file inside `projects/.venv/`, a binary file,
an empty file and a FIFO.

Default output: the path and matching lines; identical copies are listed once at the end; the
summary goes to stderr.

```console
$ findme portfolio -e py
./backup/old/portfolio.py
  3: def load_portfolio(path):

Identical copies (shown once above):
  ./backup/old/portfolio.py
    = ./projects/stocks/portfolio.py

Searched 2 files: 'portfolio' found in 1 unique file (+1 identical copy); 2 skipped.
```

(`.venv` is excluded by default; the empty file and the FIFO were skipped.)

Only the paths, case-insensitive:

```console
$ findme -i portfolio -l
./backup/old/portfolio.py
./projects/web/README.md
Searched 3 files: 'portfolio' found in 2 unique files (+1 identical copy); 3 skipped.
```

Regex, whole file printed (the original script's output style):

```console
$ findme 'def \w+_portfolio' -r projects --full
================================================================================
projects/stocks/portfolio.py
================================================================================
import csv

def load_portfolio(path):
    with open(path) as f:
        return list(csv.DictReader(f))
================================================================================

Searched 2 files: 'def \\w+_portfolio' found in 1 unique file; 3 skipped.
```

JSON for scripting:

```console
$ findme portfolio projects --json -q
{
  "phrase": "portfolio",
  "searched": 2,
  "skipped": 3,
  "hits": [
    {
      "path": "projects/stocks/portfolio.py",
      "sha256": "9593c9a518bfcbeb3f280e5193150d7f2571439dc29906d87650c9816ae596ad",
      "matches": [{"line": 3, "text": "def load_portfolio(path):"}],
      "duplicates": []
    }
  ],
  "errors": []
}
```

(JSON is shown compacted here; the real output is indented one key per line.)

Errors don't produce tracebacks:

```console
$ findme '(' -r
findme: error: invalid regular expression '(': missing ), unterminated subpattern at position 0
$ findme x nope
findme: error: no such file or directory: nope
$ findme x --max-size abc
findme: error: invalid size: 'abc' (try e.g. 512K, 10M, 1G)
```

Searching the whole machine like the original did (run on the dev box, took about 17 s):

```console
$ findme portfolio / -e py -x /proc -x /sys -x /usr/lib -l > hits.txt
Searched 24940 files: 'portfolio' found in 15 unique files (+1 identical copy); 950 skipped.
```

Piping into `head` stops cleanly (exit status 141, no traceback). Ctrl-C exits with 130.

## Configuration

Settings are layered: built-in defaults, then the config file, then environment variables, then
command-line options. Exclude patterns add up across all layers; the other settings override.

**Config file** (TOML): `--config FILE`, else `$FINDME_CONFIG`, else
`$XDG_CONFIG_HOME/findme/config.toml`, else `~/.config/findme/config.toml`. A missing default
file is fine. Unknown keys are an error.

```toml
extensions = ["py", "md"]
exclude = ["build", "*.egg-info", "/mnt/backup"]
default_excludes = true
ignore_case = false
max_size = "10M"
follow_symlinks = false
```

**Environment variables:**

| Variable | Example |
| --- | --- |
| `FINDME_EXTENSIONS` | `py,txt` |
| `FINDME_EXCLUDE` | `build:dist:/mnt/backup` (separated by `os.pathsep`, `:` on Unix) |
| `FINDME_MAX_SIZE` | `2M` |
| `FINDME_CONFIG` | `/path/to/config.toml` |

## How it works

```
src/findme/
  matcher.py   Matcher: literal or regex, optional ignore-case, returns (lineno, line)   pure
  filters.py   extensions, glob excludes, binary sniffing, decoding, SHA-256           pure
  core.py      search(paths, matcher, read): match, skip, collect errors, group copies  pure
  report.py    text / full / paths / JSON rendering, summary line                       pure
  config.py    defaults + TOML file + FINDME_* env -> Settings
  scan.py      os.walk with directory pruning, safe read_file()                         I/O
  cli.py       argparse, wiring, exit codes                                             I/O
```

* **Walking** (`scan.iter_files`) is sorted and deterministic. Excluded directories are pruned,
  so their contents are never visited. Name patterns are checked only against path components
  *below* the root you gave, so `findme foo .venv` still searches inside `.venv` on purpose.
* **Reading** (`scan.read_file`) refuses non-regular files (FIFOs, devices, sockets), which would
  otherwise hang a search of `/`, and files over `--max-size`. Permission and other OS errors are
  collected and counted rather than crashing.
* **Matching** (`core.search`) skips empty files and binary files (a NUL byte in the first 8 KiB),
  decodes text as UTF-8 with replacement characters so oddly encoded files are still searched,
  and matches line by line.
* **Deduplication**: each matching file's SHA-256 is computed from the bytes already in memory.
  The first file with a given digest is the hit; later ones are listed as its identical copies.
  Unique hits are printed as soon as they are found.

`core.search` takes the path iterable and the `read` function as arguments, so the core logic is
tested without touching the filesystem.

## Tests

```console
$ .venv/bin/pip install -e '.[dev]'
$ .venv/bin/pytest
103 passed
```

The tests use in-memory fake readers and `tmp_path` trees only; they never read your home
directory or real config (the CLI is called with an explicit, empty environment).

## Known limitations

* Only exact byte-identical files count as copies. A copy with one changed line or different line
  endings is a separate hit.
* Matching is per line: a regex cannot span lines.
* Each file is read whole into memory (capped by `--max-size`, default 10 MiB).
* Text is assumed to be UTF-8. Files in other encodings are still searched, but non-ASCII
  characters in them can't be matched reliably.
* No `.gitignore` support and no parallelism. A full search of `/` is as slow as `os.walk` plus
  reading every candidate file.
* The identical-copies list is printed after all unique hits. With `-l` it is left out, and only
  the summary count is shown.
* Only exercised on Linux. The code avoids POSIX-only calls (except the FIFO test, which is
  skipped where `mkfifo` doesn't exist), but it has not been run on Windows or macOS.
