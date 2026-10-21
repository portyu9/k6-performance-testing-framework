"""Keep Pages examples synchronized with canonical example READMEs.

The repository's examples/ tree is the source of truth. GitHub Pages only
publishes docs/. Run --sync after editing examples; CI uses --check.
"""
from __future__ import annotations

import os
import posixpath
import re
import sys
from html import unescape
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "examples"
PAGES = ROOT / "docs" / "examples"
INDEX = ROOT / "docs" / "index.md"
GITHUB_BLOB = "https://github.com/portyu9/k6-performance-testing-framework/blob/main/"
MARKDOWN_LINK = re.compile(r"(?<!!)(\[[^\]]+\]\()([^)]+)(\))")
EXAMPLES_LINK = "[Examples](examples/)"
SAMPLE_JSON = Path("summary-output/example-summary.json")


def sources() -> list[Path]:
    return [SOURCE / "README.md", *sorted(SOURCE.glob("*/README.md"))]


def published_file(source: Path) -> Path:
    return PAGES / source.relative_to(SOURCE)


def permalink(source: Path) -> str:
    rel = source.parent.relative_to(SOURCE)
    return "/examples/" + (rel.as_posix() + "/" if rel != Path(".") else "")


def page_content(source: Path) -> str:
    """Publish Markdown with Pages permalinks and context-aware link targets."""
    dest = published_file(source)
    body = source.read_text(encoding="utf-8")
    title = body.splitlines()[0].removeprefix("# ")
    if not body.startswith("# ") or not title.strip() or ":" in title:
        raise ValueError(f"unsupported example page title: {source}")

    def redirect_link(match: re.Match[str]) -> str:
        prefix, url, suffix = match.groups()
        url = unescape(url)
        if (not url or url.startswith("#") or url.startswith("//")
                or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", url)):
            return match.group(0)
        relative, marker, fragment = url.partition("#")
        path_part = relative.split("?", 1)[0]
        target = (source.parent / unquote(path_part)).resolve()
        if not target.is_relative_to(ROOT) or not target.is_file():
            raise ValueError(f"broken or escaping source example link: {source}: {url}")

        if target.is_relative_to(SOURCE) and target.suffix.lower() == ".md":
            if target not in sources():
                raise ValueError(f"unpublished example Markdown target: {target}")
            relative_link = posixpath.relpath(
                permalink(target).strip("/"), start=permalink(source).strip("/")
            )
            rewritten = relative_link if relative_link != "." else "./"
            if not rewritten.endswith("/"):
                rewritten += "/"
        elif target.is_relative_to(ROOT / "docs") and target.suffix.lower() == ".md":
            rewritten = os.path.relpath(target, dest.parent).replace(os.sep, "/")
        elif target == SOURCE / SAMPLE_JSON:
            rewritten = os.path.relpath(PAGES / SAMPLE_JSON, dest.parent).replace(os.sep, "/")
        else:
            rewritten = GITHUB_BLOB + target.relative_to(ROOT).as_posix()
        return prefix + rewritten + (marker + fragment if marker else "") + suffix

    body = MARKDOWN_LINK.sub(redirect_link, body)
    return (f"---\nlayout: default\ntitle: {title}\n"
            f"permalink: {permalink(source)}\n---\n\n" + body)


def validate_local_pages_links(doc: Path, errors: list[str]) -> None:
    """Fail when a Pages navigation link escapes docs/ or targets a missing file."""
    for _, raw, _ in MARKDOWN_LINK.findall(doc.read_text(encoding="utf-8")):
        url = unescape(raw)
        if (not url or url.startswith("#") or url.startswith("//")
                or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", url)):
            continue
        path_part = url.split("#", 1)[0].split("?", 1)[0]
        if not path_part:
            continue
        destination = (doc.parent / unquote(path_part)).resolve()
        if not destination.is_relative_to(ROOT / "docs"):
            errors.append(f"Pages link escapes published docs/: {doc.relative_to(ROOT)}: {url}")
        elif destination.is_dir() and not (destination / "README.md").is_file():
            errors.append(f"Pages directory lacks README.md: {doc.relative_to(ROOT)}: {url}")
        elif not destination.exists():
            errors.append(f"Pages link has no published target: {doc.relative_to(ROOT)}: {url}")


def validate_pages_examples(errors: list[str]) -> None:
    if not INDEX.is_file():
        errors.append("Pages entrypoint missing: docs/index.md")
        return
    if INDEX.read_text(encoding="utf-8").count(EXAMPLES_LINK) != 1:
        errors.append("Pages Start / Examples must link to the local examples/ page exactly once")
    validate_local_pages_links(INDEX, errors)

    source_files = sources()
    if not all(path.is_file() for path in source_files):
        errors.append("Canonical examples index missing: examples/README.md")
        return
    if len(source_files) < 2:
        errors.append("Pages examples must contain more than an index")
    for source in source_files:
        published = published_file(source)
        if not published.is_file():
            errors.append(f"Pages example guide missing: {published.relative_to(ROOT)}")
            continue
        try:
            expected = page_content(source)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if published.read_text(encoding="utf-8") != expected:
            errors.append(f"Pages guide stale or wrongly linked: {published.relative_to(ROOT)}; run --sync")
        validate_local_pages_links(published, errors)

    sample = SOURCE / SAMPLE_JSON
    published_sample = PAGES / SAMPLE_JSON
    if not sample.is_file() or not published_sample.is_file():
        errors.append("Pages evidence fixture missing: docs/examples/summary-output/example-summary.json")
    elif sample.read_bytes() != published_sample.read_bytes():
        errors.append("Pages evidence fixture stale: docs/examples/summary-output/example-summary.json")

    expected = {published_file(x) for x in source_files}
    actual = set(PAGES.rglob("README.md")) if PAGES.is_dir() else set()
    for orphan in sorted(actual - expected):
        errors.append(f"Orphan Pages guide: {orphan.relative_to(ROOT)}")


def sync_pages_examples() -> None:
    for source in sources():
        target = published_file(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page_content(source), encoding="utf-8")
    sample = PAGES / SAMPLE_JSON
    sample.parent.mkdir(parents=True, exist_ok=True)
    sample.write_bytes((SOURCE / SAMPLE_JSON).read_bytes())


def main() -> int:
    if sys.argv[1:] == ["--sync"]:
        sync_pages_examples()
    elif sys.argv[1:] not in ([], ["--check"]):
        print("usage: validate_pages_examples.py [--check | --sync]")
        return 2
    errors: list[str] = []
    validate_pages_examples(errors)
    if errors:
        print("Pages examples contract failed:")
        for message in errors:
            print(f"- {message}")
        return 1
    print(f"Pages examples contract: {len(sources())} rendered guides and fixture match source examples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
