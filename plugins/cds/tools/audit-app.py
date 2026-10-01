#!/usr/bin/env python3
"""audit-app — check application UI code against a cds hand-off bundle.

The deterministic half of a cds compliance check on product code. It reads the
bundle's generated stylesheet set (`styles/tokens.css`, `components.css`,
`themes.css`, `manifest.json`) as the inventory of what the design system ships
— every class its selectors name and every custom property it declares — and
flags, in the application files it is given, everything that styles the UI
outside that inventory.

Usage
-----
  audit-app.py --repo <repo> --bundle <bundle> [--files <path> ...]

  --repo     the application repository (a git work tree)
  --bundle   the cds hand-off bundle: a `batch-*` or `<change>-<timestamp>`
             directory holding `styles/`, or a stylesheet directory itself
  --files    the files to audit, relative to --repo. Without it, the files the
             work tree changed against HEAD (modified, added and untracked;
             deleted files excluded) are audited.

Rules
-----
  raw-color                 a hex, rgb(), hsl() or other color-function literal
  raw-length                a non-zero px, rem or em value
  inline-style              a style= attribute
  own-stylesheet            a stylesheet the bundle does not ship (anything but a
                            byte copy of a bundle sheet or an entry file holding
                            only @import / @charset / @layer / @use / @forward),
                            a <style> block, or CSS-in-JS
  token-override            product code declares a custom property the bundle
                            declares
  unknown-custom-property   a custom property declared or read with var() that
                            the bundle does not declare
  review-harness            a review-harness class (rv-*, cds-review-*), which
                            the built app never emits
  unknown-class             a class name the bundle's selectors do not name

Every finding carries a `ruling`: `violation` for a rule the script decides, and
`judgment` for `unknown-class`, which the script cannot rule on alone — the class
may be a behaviour hook that carries no styling, a third-party library's class,
or a component cds does not cover yet. A judgment finding goes to the
audit-against-system skill.

Output
------
One JSON object on stdout: the script version, the bundle, the files audited and
skipped, and each finding as {file, line, rule, value, ruling}. Exit status 0
when there is no finding, 1 when there is at least one, 2 on a usage or IO error
(the JSON then carries `error`).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_ROOT / "lib"))

import cds_hash  # noqa: E402

BUNDLE_SHEETS = ("tokens.css", "components.css", "themes.css")

MARKUP_SUFFIXES = frozenset(
    {".tsx", ".jsx", ".vue", ".svelte", ".html", ".htm", ".astro", ".mdx"}
)
STYLE_SUFFIXES = frozenset({".css", ".scss", ".sass", ".less", ".pcss", ".styl"})
TEST_NAME = re.compile(r"\.(test|spec|stories|story)\.[^/]+$")
TEST_DIRS = frozenset(
    {"__tests__", "__snapshots__", "tests", "test", "e2e", "cypress", "playwright"}
)

VIOLATION = "violation"
JUDGMENT = "judgment"

HEX_COLOR = re.compile(
    r"(?<![\w&#/-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])"
)
COLOR_FUNCTION = re.compile(
    r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(\s*[^)]*\)?", re.IGNORECASE
)
LENGTH = re.compile(r"(?<![\w.$#-])(\d*\.?\d+)(px|rem|em)\b")
VAR_REFERENCE = re.compile(r"var\(\s*(--[\w-]+)")
LINK_ATTRIBUTE = re.compile(
    r"\b(?:href|to|id|xlink:href|src|action|for|name|key)\s*=\s*\{?\s*[\"'`]?$"
)
INLINE_STYLE = re.compile(r"(?<![\w-])style\s*=\s*(?=[\"'{])")
STYLE_BLOCK = re.compile(r"<style\b", re.IGNORECASE)
CSS_IN_JS = re.compile(
    r"\b(?:styled(?:\.\w+|\([^)]*\))(?:\.attrs\([^)]*\))?|css|createGlobalStyle|keyframes)\s*`"
    r"|\bmakeStyles\s*\(|(?<![\w-])sx\s*=\s*\{"
)
CLASS_ATTRIBUTE = re.compile(r"(?<![\w-])(?:class|className|class:list)\s*=\s*")
CLASS_HELPER = re.compile(r"\b(?:clsx|cn|cx|classNames|classnames|twMerge)\s*\(")
STRING_LITERAL = re.compile(
    r"\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*'|`(?:[^`\\]|\\.)*`", re.DOTALL
)
TEMPLATE_HOLE = re.compile(r"\$\{[^}]*\}")
CLASS_TOKEN = re.compile(r"^-?[_a-zA-Z][\w:/\[\]().%#,-]*$")
HARNESS_CLASS = re.compile(r"^(?:rv-|cds-review-)")
SELECTOR_CLASS = re.compile(r"(?<![\w-])\.(-?[_a-zA-Z][\w-]*)")
CUSTOM_PROPERTY_DECLARATION = re.compile(r"(--[\w-]+)\s*:")
DECLARATION = re.compile(r"(-{0,2}[\w-]+)\s*:\s*([^;{}]+)")
ENTRY_STATEMENT = re.compile(r"@(?:import|charset|layer|use|forward)\b[^;{}]*;")
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
LINE_COMMENT = re.compile(r"(?<![:\w\"'`/])//[^\n]*")

SNIPPET = 120


class AuditError(Exception):
    """A usage or IO problem that stops the audit."""


def _blank(match: re.Match) -> str:
    """Return the match with every character but a newline replaced by a space."""
    return re.sub(r"[^\n]", " ", match.group(0))


def _strip_comments(text: str, *, markup: bool) -> str:
    """Return the text with its comments blanked, keeping every offset and line number.

    Returns:
        The text, the same length, with comments replaced by spaces.
    """
    text = BLOCK_COMMENT.sub(_blank, text)
    if markup:
        text = HTML_COMMENT.sub(_blank, text)
        text = LINE_COMMENT.sub(_blank, text)
    return text


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def plugin_version() -> str:
    """Return the cds plugin version this script ships in.

    Returns:
        The version from the plugin's plugin.json, or "unknown".
    """
    try:
        meta = json.loads(
            (_PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, ValueError):
        return "unknown"
    return str(meta.get("version") or "unknown")


def styles_dir(bundle: Path) -> Path:
    """Return the bundle's stylesheet directory.

    Returns:
        `<bundle>/styles` when it holds the sheets, else the bundle itself.

    Raises:
        AuditError: neither holds tokens.css.
    """
    for candidate in (bundle / "styles", bundle):
        if (candidate / "tokens.css").is_file():
            return candidate
    raise AuditError(f"{bundle} holds no styles/tokens.css: it is not a cds bundle")


def inventory(styles: Path) -> dict:
    """Read what the bundle ships from its stylesheet set.

    Returns:
        The class names its selectors name, the custom properties it declares, the
        SHA-256 of each sheet, and whether every sheet matches manifest.json.

    Raises:
        AuditError: a sheet cannot be read.
    """
    classes: set[str] = set()
    properties: set[str] = set()
    hashes: dict[str, str] = {}
    for name in BUNDLE_SHEETS:
        path = styles / name
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise AuditError(f"cannot read {path}: {exc}") from exc
        hashes[name] = cds_hash._sha256_hex(raw)  # noqa: SLF001
        text = _strip_comments(raw.decode("utf-8", errors="replace"), markup=False)
        properties.update(CUSTOM_PROPERTY_DECLARATION.findall(text))
        for selector in re.findall(r"([^{};]*)\{", text):
            if selector.strip().startswith("@"):
                continue
            classes.update(SELECTOR_CLASS.findall(selector))
    try:
        manifest = json.loads((styles / "manifest.json").read_text(encoding="utf-8"))
        recorded = manifest.get("files") or {}
        verified = all(recorded.get(name) == digest for name, digest in hashes.items())
        fingerprint = manifest.get("elements_semantic_sha256")
    except (OSError, ValueError):
        verified, fingerprint = False, None
    return {
        "classes": classes,
        "properties": properties,
        "hashes": set(hashes.values()),
        "verified": verified,
        "fingerprint": fingerprint,
    }


def _git(repo: Path, *argv: str) -> list[str]:
    try:
        done = subprocess.run(  # noqa: S603
            ["git", "-C", str(repo), *argv],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise AuditError(f"git could not run: {exc}") from exc
    if done.returncode != 0:
        raise AuditError(
            f"git {' '.join(argv)} failed in {repo}: {done.stderr.strip()}"
        )
    return [line for line in done.stdout.splitlines() if line.strip()]


def changed_files(repo: Path) -> list[str]:
    """Return the files the work tree changed against HEAD, untracked ones included.

    Returns:
        Repository-relative paths, deleted files excluded, sorted.
    """
    tracked = _git(repo, "diff", "--name-only", "--diff-filter=ACMR", "HEAD")
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard")
    return sorted(set(tracked) | set(untracked))


def _skip_reason(rel: str) -> str | None:
    path = Path(rel)
    suffix = path.suffix.lower()
    if suffix not in MARKUP_SUFFIXES and suffix not in STYLE_SUFFIXES:
        return "not a markup or stylesheet file"
    if TEST_NAME.search(path.name) or TEST_DIRS.intersection(path.parts[:-1]):
        return "a test or story file"
    return None


class FileAudit:
    """The findings for one file."""

    def __init__(self, rel: str, text: str, inv: dict) -> None:
        self.rel = rel
        self.text = text
        self.inv = inv
        self.findings: list[dict] = []

    def add(self, offset: int, rule: str, value: str, ruling: str = VIOLATION) -> None:
        self.findings.append(
            {
                "file": self.rel,
                "line": _line_of(self.text, offset),
                "rule": rule,
                "value": " ".join(value.split())[:SNIPPET],
                "ruling": ruling,
            }
        )

    def scan_values(self, text: str, start: int = 0, end: int | None = None) -> None:
        """Flag raw colors, raw lengths and unknown var() references in text[start:end]."""
        region = text[start:end]
        for m in HEX_COLOR.finditer(region):
            before = region[max(0, m.start() - 24) : m.start()]
            if LINK_ATTRIBUTE.search(before):
                continue
            self.add(start + m.start(), "raw-color", m.group(0))
        for m in COLOR_FUNCTION.finditer(region):
            self.add(start + m.start(), "raw-color", m.group(0))
        for m in LENGTH.finditer(region):
            if float(m.group(1)) == 0:
                continue
            self.add(start + m.start(), "raw-length", m.group(0))
        for m in VAR_REFERENCE.finditer(region):
            if m.group(1) not in self.inv["properties"]:
                self.add(start + m.start(), "unknown-custom-property", m.group(1))

    def stylesheet(self, raw: bytes) -> None:
        """Audit a stylesheet the change carries."""
        if cds_hash._sha256_hex(raw) in self.inv["hashes"]:  # noqa: SLF001
            return
        text = _strip_comments(self.text, markup=False)
        if not ENTRY_STATEMENT.sub("", text).strip():
            return
        self.add(
            0,
            "own-stylesheet",
            f"{self.rel}: a stylesheet the cds bundle does not ship",
        )
        for m in DECLARATION.finditer(text):
            prop = m.group(1)
            if prop.startswith("--"):
                rule = (
                    "token-override"
                    if prop in self.inv["properties"]
                    else "unknown-custom-property"
                )
                self.add(m.start(), rule, prop)
            self.scan_values(text, m.start(2), m.end(2))

    def _class_strings(self, text: str) -> list[tuple[int, str]]:
        """Return (offset, literal) for each string that holds class names."""
        out: list[tuple[int, str]] = []
        for opener in (*CLASS_ATTRIBUTE.finditer(text), *CLASS_HELPER.finditer(text)):
            i = opener.end()
            if opener.re is CLASS_HELPER:
                span = _balanced(text, i - 1, "(", ")")
            elif i < len(text) and text[i] in "\"'":
                close = text.find(text[i], i + 1)
                span = (i, close + 1) if close > i else None
            elif i < len(text) and text[i] == "{":
                span = _balanced(text, i, "{", "}")
            else:
                span = None
            if span is None:
                continue
            chunk = text[span[0] : span[1]]
            if chunk[:1] in "\"'":
                out.append((span[0] + 1, chunk[1:-1]))
                continue
            for lit in STRING_LITERAL.finditer(chunk):
                out.append((span[0] + lit.start() + 1, lit.group(0)[1:-1]))
        return out

    def markup(self) -> None:
        """Audit a markup or component file."""
        text = _strip_comments(self.text, markup=True)
        for m in INLINE_STYLE.finditer(text):
            self.add(
                m.start(),
                "inline-style",
                text[m.start() : m.start() + SNIPPET].split("\n")[0],
            )
        for m in STYLE_BLOCK.finditer(text):
            self.add(m.start(), "own-stylesheet", "<style> block")
        for m in CSS_IN_JS.finditer(text):
            self.add(m.start(), "own-stylesheet", m.group(0))
        for m in CUSTOM_PROPERTY_DECLARATION.finditer(text):
            prop = m.group(1)
            rule = (
                "token-override"
                if prop in self.inv["properties"]
                else "unknown-custom-property"
            )
            self.add(m.start(), rule, prop)
        self.scan_values(text)
        seen: set[tuple[int, str]] = set()
        for offset, literal in self._class_strings(text):
            for token in TEMPLATE_HOLE.sub(" ", literal).split():
                if not CLASS_TOKEN.match(token) or token in self.inv["classes"]:
                    continue
                key = (_line_of(text, offset), token)
                if key in seen:
                    continue
                seen.add(key)
                if HARNESS_CLASS.match(token):
                    self.add(offset, "review-harness", token)
                else:
                    self.add(offset, "unknown-class", token, JUDGMENT)


def _balanced(
    text: str, start: int, opening: str, closing: str
) -> tuple[int, int] | None:
    """Return the span from text[start] (an opening bracket) to its closing bracket.

    Returns:
        (start, end) with end past the closing bracket, or None when it never closes.
    """
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch in "\"'`":
            lit = STRING_LITERAL.match(text, i)
            if lit:
                i = lit.end()
                continue
        if ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    return None


def audit(repo: Path, bundle: Path, files: list[str] | None) -> dict:
    """Run the audit and return its report.

    Returns:
        The report object written to stdout.

    Raises:
        AuditError: the repository, the bundle or a file cannot be read.
    """
    if not repo.is_dir():
        raise AuditError(f"{repo} is not a directory")
    styles = styles_dir(bundle)
    inv = inventory(styles)
    targets = files if files is not None else changed_files(repo)
    audited: list[str] = []
    skipped: list[dict] = []
    findings: list[dict] = []
    for rel in targets:
        reason = _skip_reason(rel)
        path = repo / rel
        if reason is None and not path.is_file():
            reason = "not a file in the work tree"
        if reason:
            skipped.append({"file": rel, "reason": reason})
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise AuditError(f"cannot read {path}: {exc}") from exc
        one = FileAudit(rel, raw.decode("utf-8", errors="replace"), inv)
        if path.suffix.lower() in STYLE_SUFFIXES:
            one.stylesheet(raw)
        else:
            one.markup()
        audited.append(rel)
        findings.extend(one.findings)
    findings.sort(key=lambda f: (f["file"], f["line"], f["rule"], f["value"]))
    return {
        "scriptVersion": plugin_version(),
        "repo": str(repo),
        "bundle": str(bundle),
        "bundleFingerprint": inv["fingerprint"],
        "bundleVerified": inv["verified"],
        "audited": audited,
        "skipped": skipped,
        "findings": findings,
        "counts": {
            "violation": sum(1 for f in findings if f["ruling"] == VIOLATION),
            "judgment": sum(1 for f in findings if f["ruling"] == JUDGMENT),
        },
        "clean": not findings,
    }


def main(argv: list[str]) -> int:
    """Parse the arguments, run the audit and print its report.

    Returns:
        0 when clean, 1 with findings, 2 on a usage or IO error.
    """
    parser = argparse.ArgumentParser(
        description="Audit application UI code against a cds bundle."
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--files", nargs="*")
    ns = parser.parse_args(argv)
    try:
        report = audit(Path(ns.repo).resolve(), Path(ns.bundle).resolve(), ns.files)
    except AuditError as exc:
        print(json.dumps({"scriptVersion": plugin_version(), "error": str(exc)}))
        return 2
    print(json.dumps(report, indent=2))
    return 0 if report["clean"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
