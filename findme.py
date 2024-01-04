import hashlib
import os
from collections import defaultdict
from mmap import mmap, ACCESS_READ


has_extension = lambda file, ext: os.path.splitext(file)[1].lstrip(".") == ext
is_current = lambda path: os.path.abspath(path) == os.path.abspath(__file__)
is_empty = lambda path: os.stat(path).st_size == 0
is_excluded = lambda path, excluded: any(e in path for e in excluded)


def compute_hash_plain(path, algorithm, block_size=8192):
    assert hasattr(hashlib, algorithm)

    _hash = getattr(hashlib, algorithm)

    def compute(path, block_size):
        nonlocal _hash

        with open(path, "rb") as f:
            _hash = _hash()
            while chunk := f.read(block_size):
                _hash.update(chunk)
            return _hash.hexdigest()

    return compute(path, block_size)


def compute_hash_mmap(path, algorithm):
    assert hasattr(hashlib, algorithm)

    _hash = getattr(hashlib, algorithm)

    def compute(path):
        nonlocal _hash

        with open(path) as file, mmap(file.fileno(), 0, access=ACCESS_READ) as file:
            return _hash(file).hexdigest()

    return compute(path)


def iterlines(filepath):
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line:
                yield line


def cat(filepath):
    with open(filepath) as f:
        return f.read()


def iterfiles(rootpath="."):
    for root_dir, dirs, files in os.walk(rootpath):
        for file in files:
            yield (file, os.path.join(root_dir, file))


def conditional_iterfiles(rootpath=".", excluded=None, extension=None, show_empty=False):
    for file, path in iterfiles(rootpath):
        if excluded is not None and is_excluded(path, excluded):
            continue

        try:
            if extension is not None and not has_extension(file, extension):
                continue

            if not show_empty and is_empty(path):
                continue
        except FileNotFoundError:
            continue

        yield path


def main():
    excluded = (
        ".venv",
        ".git",
        ".config",
        "cache",
        "site-packages",
        "dist-packages",
        "python-skeletons",
        "flatpak",
        "pycharm",
        "node_modules",
        "/usr/lib/python",
    )
    target_ext = "py"
    search_phrase = "portfolio"

    num_files = 0
    how_many_contain = 0

    checksums = defaultdict(list)

    for path in conditional_iterfiles(
        rootpath="/",
        excluded=excluded,
        extension=target_ext,
    ):
        if is_current(path):
            continue

        num_files += 1

        found = False
        try:
            for line in iterlines(path):
                if search_phrase in line:
                    found = True
                    break
        except UnicodeDecodeError:
            pass

        if found:
            checksum = compute_hash_mmap(path, "sha256")

            if checksum in checksums:
                print(f"Skipping, same file was already processed.")
                continue

            how_many_contain += 1
            print("=" * 80)
            print(f"Found in {path}")
            print("=" * 80)
            print(cat(path).strip())
            print("=" * 80)
            print()

            checksums[checksum].append(path)

    print(f"Searched in {num_files} files.")
    print(f"`{search_phrase}` was found in {how_many_contain} files meeting criteria.")


if __name__ == "__main__":
    main()