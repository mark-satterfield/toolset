#!/usr/bin/env python3
"""
cds_hash — deterministic input fingerprints for the CDS stylesheet pipeline.

ONE implementation, shared by `generate-stylesheets` (which writes the manifest)
and the composers (`compose-page` / `compose-app-surface`, which read the
manifest to decide whether the stylesheet set is stale). Sharing one script is
the point: the writer and the readers can never disagree on what "the inputs
changed" means.

Subcommands
-----------
  semantic <elements.yaml>
      Print the SEMANTIC SHA-256 of the elements YAML — the hash of its MEANING,
      not its bytes. Parsing drops comments and formatting; every `description:`
      value (human prose) is then removed; the remaining structure is serialized
      canonically in FILE ORDER. Key order is load-bearing — `generate-stylesheets`
      walks the YAML blocks in file order and emits tokens in that order, so a
      reordering legitimately changes the emitted CSS and therefore the hash.
      A comment-only or description-only edit does NOT change this hash, so it
      does NOT trigger a regeneration.

  reference-tree <reference-dir>
      Print the SHA-256 of the reference tree: the hash of the
      alphabetically-sorted concatenation of every file's tree-relative path plus
      that file's own SHA-256, across the whole tree.

  extensions-tree <dir|NONE>
      The same tree hash for a project's extensions directory. When the argument
      is "NONE" or the directory does not exist, print the stable SHA-256 of the
      empty string, so "no extensions" always hashes the same way.

  inputs <elements.yaml> <reference-dir> <extensions-dir|NONE>
      Print a JSON object with all three fingerprints — the call the skills make:
        {"elements_semantic_sha256": "...",
         "reference_tree_sha256": "...",
         "extensions_tree_sha256": "..."}

Exit status: 0 on success; 2 on usage or IO error (message on stderr).
"""
import hashlib
import json
import os
import sys

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a declared plugin dependency
    sys.stderr.write("cds_hash: PyYAML required (pip install pyyaml)\n")
    sys.exit(2)


def _sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


_EMPTY_SENTINEL = _sha256_hex(b"")


def _strip_descriptions(node):
    """Return a copy of `node` with every mapping key named 'description'
    removed at any nesting depth. Lists are walked element-wise; scalars pass
    through. The input is never mutated."""
    if isinstance(node, dict):
        return {
            k: _strip_descriptions(v)
            for k, v in node.items()
            if k != "description"
        }
    if isinstance(node, list):
        return [_strip_descriptions(v) for v in node]
    return node


def semantic_hash(yaml_path):
    """SHA-256 of the elements YAML's meaning: comments/formatting dropped by
    parsing, every `description:` value removed, the rest serialized canonically
    in file order."""
    with open(yaml_path, "rb") as f:
        data = yaml.safe_load(f.read())
    pruned = _strip_descriptions(data)
    # sort_keys=False is deliberate — key order is part of the meaning that
    # affects the emitted CSS (the generator emits tokens in YAML order).
    canon = json.dumps(
        pruned, ensure_ascii=False, separators=(",", ":"), sort_keys=False
    )
    return _sha256_hex(canon.encode("utf-8"))


def _tree_files(root):
    """(relpath, abspath) for every file under root, sorted by relpath."""
    items = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            ap = os.path.join(dirpath, fn)
            items.append((os.path.relpath(ap, root), ap))
    items.sort(key=lambda t: t[0])
    return items


def tree_hash(root):
    """SHA-256 over the sorted concatenation of each file's relpath + its own
    content SHA-256. Reflects both renames and content changes."""
    h = hashlib.sha256()
    for relpath, abspath in _tree_files(root):
        with open(abspath, "rb") as f:
            file_hex = _sha256_hex(f.read())
        h.update(relpath.replace(os.sep, "/").encode("utf-8"))
        h.update(b"\0")
        h.update(file_hex.encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def extensions_tree_hash(arg):
    if arg == "NONE" or not arg or not os.path.isdir(arg):
        return _EMPTY_SENTINEL
    return tree_hash(arg)


def _usage(code=2):
    sys.stderr.write(
        "usage: cds_hash.py <semantic|reference-tree|extensions-tree|inputs> "
        "<args...>\n"
    )
    sys.exit(code)


def main(argv):
    if len(argv) < 2:
        _usage()
    cmd = argv[1]
    try:
        if cmd == "semantic":
            if len(argv) != 3:
                _usage()
            print(semantic_hash(argv[2]))
        elif cmd == "reference-tree":
            if len(argv) != 3:
                _usage()
            print(tree_hash(argv[2]))
        elif cmd == "extensions-tree":
            if len(argv) != 3:
                _usage()
            print(extensions_tree_hash(argv[2]))
        elif cmd == "inputs":
            if len(argv) != 5:
                _usage()
            out = {
                "elements_semantic_sha256": semantic_hash(argv[2]),
                "reference_tree_sha256": tree_hash(argv[3]),
                "extensions_tree_sha256": extensions_tree_hash(argv[4]),
            }
            print(json.dumps(out, indent=2))
        else:
            _usage()
    except (FileNotFoundError, OSError) as e:
        sys.stderr.write(f"cds_hash: {e}\n")
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv)
