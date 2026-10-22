"""Command-line interface for findme."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Mapping, Sequence, TextIO

from findme import __version__
from findme.config import ConfigError, load_settings, parse_size
from findme.core import Hit, SearchError, search
from findme.filters import DEFAULT_EXCLUDES, normalize_extensions
from findme.matcher import Matcher
from findme.report import format_duplicates, format_hit, format_json, format_summary
from findme.scan import iter_files, read_file

EXIT_FOUND, EXIT_NOT_FOUND, EXIT_ERROR = 0, 1, 2

EPILOG = """\
exit status: 0 if something was found, 1 if nothing was found, 2 on errors.

environment:
  FINDME_EXTENSIONS   default extensions, comma separated (e.g. "py,txt")
  FINDME_EXCLUDE      extra exclude patterns, separated by '{sep}'
  FINDME_MAX_SIZE     default --max-size
  FINDME_CONFIG       config file path (default: $XDG_CONFIG_HOME/findme/config.toml)

examples:
  findme portfolio ~/code -e py         where did I use "portfolio"?
  findme -i 'TODO' . -l                 list unique files with a TODO
  findme 'def \\w+_hash' -r src --full    dump whole files matching a regex
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="findme",
        description=(
            "Find files containing a phrase, show where it matches, and show "
            "byte-identical copies only once."
        ),
        epilog=EPILOG.format(sep=os.pathsep),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("phrase", help="text to look for (a regex with -r)")
    p.add_argument("roots", nargs="*", metavar="ROOT", help="files or directories to search (default: .)")

    sel = p.add_argument_group("what to search")
    sel.add_argument(
        "-e", "--ext", dest="extensions", action="append", metavar="EXT",
        help="only files with this extension; repeatable or comma separated (default: all)",
    )
    sel.add_argument(
        "-x", "--exclude", dest="excludes", action="append", default=[], metavar="GLOB",
        help="skip paths matching GLOB (a name like 'build' or a path like '/usr/lib'); repeatable",
    )
    sel.add_argument(
        "--no-default-excludes", action="store_true",
        help="also search " + ", ".join(DEFAULT_EXCLUDES[:4]) + ", ... (see README)",
    )
    sel.add_argument("--max-size", metavar="SIZE", help="skip files larger than SIZE, e.g. 512K, 10M, 0=unlimited (default: 10M)")
    sel.add_argument("-L", "--follow-symlinks", action="store_true", default=None, help="follow symbolic links")

    mat = p.add_argument_group("how to match")
    mat.add_argument("-i", "--ignore-case", action="store_true", default=None, help="case-insensitive match")
    mat.add_argument("-r", "--regex", action="store_true", help="treat PHRASE as a Python regular expression")

    out = p.add_argument_group("output")
    mode = out.add_mutually_exclusive_group()
    mode.add_argument("--full", dest="mode", action="store_const", const="full", help="print each matching file in full")
    mode.add_argument("-l", "--files-only", dest="mode", action="store_const", const="paths", help="print only paths of unique matching files")
    mode.add_argument("--json", dest="mode", action="store_const", const="json", help="print a JSON report")
    out.add_argument("-q", "--quiet", action="store_true", help="no summary line on stderr")
    out.add_argument("-v", "--verbose", action="store_true", help="report every unreadable file on stderr")

    cfg = p.add_argument_group("configuration")
    cg = cfg.add_mutually_exclusive_group()
    cg.add_argument("--config", metavar="FILE", help="read settings from this TOML file")
    cg.add_argument("--no-config", action="store_true", help="ignore the config file")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


EXIT_BROKEN_PIPE = 141  # 128 + SIGPIPE, what shells report for `findme ... | head`


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    environ = os.environ if environ is None else environ
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        return _run(argv, environ, stdout, stderr)
    except KeyboardInterrupt:
        print("findme: interrupted", file=stderr)
        return 130
    except BrokenPipeError:
        # The reader went away (e.g. `| head`). Silence further writes to the
        # real stdout so Python doesn't complain while flushing at exit.
        if stdout is sys.stdout:
            try:
                devnull = os.open(os.devnull, os.O_WRONLY)
                os.dup2(devnull, sys.stdout.fileno())
            except (OSError, ValueError):  # pragma: no cover - best effort
                pass
        return EXIT_BROKEN_PIPE


def _run(
    argv: Sequence[str] | None,
    environ: Mapping[str, str],
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    def fail(message: str) -> int:
        print(f"findme: error: {message}", file=stderr)
        return EXIT_ERROR

    try:
        settings = load_settings(environ, config_path=args.config, use_config=not args.no_config)
        max_size = parse_size(args.max_size) if args.max_size is not None else settings.max_size
    except ConfigError as exc:
        return fail(str(exc))

    extensions = normalize_extensions(args.extensions) if args.extensions else settings.extensions
    excludes = settings.excludes + tuple(args.excludes)
    if settings.default_excludes and not args.no_default_excludes:
        excludes = DEFAULT_EXCLUDES + excludes
    ignore_case = settings.ignore_case if args.ignore_case is None else True
    follow = settings.follow_symlinks if args.follow_symlinks is None else True

    try:
        matcher = Matcher(args.phrase, regex=args.regex, ignore_case=ignore_case)
    except ValueError as exc:
        return fail(str(exc))

    roots = args.roots or ["."]
    missing = [r for r in roots if not os.path.exists(r)]
    if missing:
        return fail(f"no such file or directory: {', '.join(missing)}")

    mode = args.mode or "lines"
    walk_errors: list[tuple[str, str]] = []

    def on_walk_error(path: str, message: str) -> None:
        walk_errors.append((path, message))

    def on_hit(hit: Hit) -> None:
        print(format_hit(hit, mode), file=stdout, flush=True)

    paths = iter_files(roots, excludes=excludes, extensions=extensions, follow_symlinks=follow, on_error=on_walk_error)
    report = search(
        paths,
        matcher,
        lambda path: read_file(path, max_size=max_size),
        keep_text=(mode == "full"),
        on_hit=None if mode == "json" else on_hit,
    )

    report.errors[:0] = [SearchError(p, m) for p, m in walk_errors]

    if mode == "json":
        print(format_json(report, args.phrase), file=stdout)
    elif mode != "paths":
        dups = format_duplicates(report)
        if dups:
            print(dups, file=stdout)

    if args.verbose:
        for err in report.errors:
            print(f"findme: {err.path}: {err.message}", file=stderr)
    if not args.quiet:
        print(format_summary(report, args.phrase), file=stderr)

    return EXIT_FOUND if report.hits else EXIT_NOT_FOUND


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
