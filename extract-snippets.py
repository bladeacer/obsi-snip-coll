#!/usr/bin/env python3
"""Extract CSS snippets from Obsidian theme files using
obsi-snip-coll markers."""
import os
import re
import json
import sys
import argparse
from pathlib import Path
from ast import literal_eval
from typing import (Any, Dict, List, Optional, Tuple)

INDEX_FILE = Path("snippets/index.json")
METADATA_FILE = Path("snippets/metadata.json")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract CSS snippets from Obsidian theme files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s                     # interactive mode\n"
            "  %(prog)s -y                  # auto-accept weak matches\n"
            "  %(prog)s -n                  # non-interactive, use defaults\n"
            "  %(prog)s -ny                 # fully automatic mode\n"
            "  %(prog)s --validate          # check metadata.json\n"
        ),
    )
    parser.add_argument(
        "-y", "--yes", action="store_true",
        help="auto-accept weak matches without prompting")
    parser.add_argument(
        "-n", "--non-interactive", action="store_true",
        help="non-interactive mode: use defaults without prompting")
    parser.add_argument(
        "--validate", action="store_true",
        help="validate metadata.json against files and exit")
    parser.add_argument(
        "-e", "--env", dest="env_path", default=None,
        help="path to .env file (default: ./.env)")
    return parser.parse_args()


def load_env(env_path: Optional[Path] = None) -> Dict[str, str]:
    """Load environment variables from a .env file."""
    if env_path is None:
        env_path = Path('.env')
    env_vars: Dict[str, str] = {}
    if not env_path.exists():
        return env_vars
    content = env_path.read_text(encoding='utf-8')
    sources_match = re.search(
        r"SOURCES\s*=\s*(\[.*?\])", content, re.DOTALL)
    if sources_match:
        env_vars['SOURCES'] = sources_match.group(1).strip()
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line and not line.startswith('SOURCES'):
            key, value = line.split('=', 1)
            env_vars[key.strip()] = value.strip().strip('\'" ')
    return env_vars


def parse_sources(
    env_vars: Dict[str, str]
) -> List[Dict[str, Optional[str]]]:
    """Parse the SOURCES variable from .env."""
    sources_str = env_vars.get("SOURCES")
    if sources_str:
        try:
            parsed = literal_eval(sources_str)
            if (isinstance(parsed, list)
                    and all(isinstance(item, dict) for item in parsed)):
                return parsed
            else:
                raise ValueError(
                    "Unsupported SOURCES format. "
                    "Expected a list of dictionaries.")
        except (ValueError, SyntaxError) as e:
            print(
                "Warning: Could not parse SOURCES from .env. "
                f"Falling back to single source format. Error: {e}")
    return [{
        "SOURCE_PATH": env_vars.get("SOURCE_PATH"),
        "SOURCE_NAME": env_vars.get("SOURCE_NAME"),
        "AUTHOR": env_vars.get("AUTHOR"),
        "LICENSE": env_vars.get("LICENSE"),
        "REPO_URL": env_vars.get("REPO_URL"),
    }]


def load_json(path: Path) -> dict:
    """Load a JSON file, returning an empty dict if not found or
    corrupted."""
    if not path.exists():
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_json(path: Path, data: dict) -> None:
    """Save a JSON file with sorted keys for deterministic output."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, sort_keys=True)
    except Exception as e:
        print(f"Error saving {path}: {e}")


def build_filtered_lines_map(
    content: str
) -> Dict[int, int]:
    """Create a mapping from original line numbers to 'code-only' line
    numbers, ignoring comments and blank lines."""
    filtered_map: Dict[int, int] = {}
    counter = 0
    in_comment_block = False
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if '/*' in stripped and '*/' not in stripped:
            in_comment_block = True
        if '*/' in stripped and '/*' not in stripped:
            in_comment_block = False
        is_code = False
        if not in_comment_block and stripped:
            if (not stripped.startswith('/*')
                    or not stripped.endswith('*/')):
                is_code = True
        if is_code:
            counter += 1
        filtered_map[i] = counter
    return filtered_map


def parse_index_key(
    key: str
) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[int]]:
    """Parse a JSON index key to extract components."""
    parts = key.rsplit('_', 3)
    if len(parts) == 4:
        source_name, file_name, line_start, line_end = parts
        try:
            return (source_name, file_name,
                    int(line_start), int(line_end))
        except (ValueError, IndexError):
            pass
    return (None, None, None, None)


def minify_css(css_content: str) -> str:
    """Remove comments and all whitespace for content comparison."""
    minified = re.sub(r'/\*.*?\*/', '', css_content, flags=re.DOTALL)
    minified = re.sub(r'\s', '', minified)
    return minified


def build_markdown(
    source_name: str,
    source: Dict[str, Optional[str]],
    snippet_name: str,
    description: str,
    css_filename: str,
) -> str:
    """Build markdown documentation content."""
    author = source.get("AUTHOR", "Unknown Author")
    repo_url = source.get("REPO_URL", "")
    licence_name = source.get("LICENSE", "MIT")
    title = snippet_name.replace('-', ' ').title()
    auto_line = (
        "This snippet was automatically extracted from the "
        f"`{source_name}` theme.")
    return f"""\
---
author: {author}
source: {repo_url}
license: {licence_name}
---

# {title}

{description}

{auto_line}

[View this file](./{css_filename})
"""


def save_metadata_entry(
    metadata: dict,
    source_name: str,
    snippet_name: str,
    sub_directory: str,
    description: str,
) -> None:
    """Save a snippet entry to the metadata dict (in-memory)."""
    if source_name not in metadata:
        metadata[source_name] = {}
    metadata[source_name][snippet_name] = {
        "sub_directory": sub_directory,
        "description": description,
    }


def write_css_and_md(
    css_content: str,
    css_path: Path,
    md_path: Path,
    source_name: str,
    source: Dict[str, Optional[str]],
    snippet_name: str,
    description: str,
) -> bool:
    """Write CSS and MD files, returning True on success."""
    try:
        css_path.parent.mkdir(parents=True, exist_ok=True)
        css_path.write_text(css_content, encoding='utf-8')
        print(f"  [OK] CSS  -> {css_path}")
    except Exception as e:
        print(f"  [ERR] CSS -> {css_path}: {e}")
        return False
    try:
        md_content = build_markdown(
            source_name, source, snippet_name, description,
            css_path.name)
        md_path.write_text(md_content, encoding='utf-8')
        print(f"  [OK] MD   -> {md_path}")
    except Exception as e:
        print(f"  [ERR] MD  -> {md_path}: {e}")
        return False
    return True


def validate_metadata(
    metadata: dict,
    index: dict,
    sources: List[Dict[str, Optional[str]]],
) -> List[str]:
    """Validate metadata.json consistency against index and files on
    disk."""
    issues: List[str] = []
    index_source_names: set = set()
    for key in index:
        src_name, _, _, _ = parse_index_key(key)
        if src_name:
            index_source_names.add(src_name)
    if not index_source_names:
        index_source_names = {
            s.get("SOURCE_NAME")
            for s in sources if s.get("SOURCE_NAME")
        }

    for source_name in index_source_names:
        source_meta = metadata.get(source_name, {})
        snippet_to_info: Dict[str, Tuple[str, str]] = {}
        for key, path in index.items():
            src_name, _, _, _ = parse_index_key(key)
            if src_name == source_name:
                p = Path(path)
                name = p.stem
                snippet_to_info[name] = (p.parent.name, key)

        for sname, sinfo in source_meta.items():
            expected_subdir = sinfo.get("sub_directory", "")
            if sname not in snippet_to_info:
                issues.append(
                    f"  '{source_name}/{sname}': in metadata.json "
                    "but no matching file in index")
                continue
            actual_subdir, _ = snippet_to_info[sname]
            if expected_subdir != actual_subdir:
                issues.append(
                    f"  '{source_name}/{sname}': "
                    f"metadata subdir '{expected_subdir}' "
                    f"but actual '{actual_subdir}'")

        for sname, (actual_subdir, key) in snippet_to_info.items():
            if sname not in source_meta:
                issues.append(
                    f"  '{source_name}/{sname}': "
                    "in index but no metadata entry")

    return issues


def process_source(
    source_data: Dict[str, Optional[str]],
    index: dict,
    metadata: dict,
    args: argparse.Namespace,
    stats: Dict[str, int],
) -> None:
    """Process a single source file, extracting and saving snippets."""
    source_path_val = source_data.get("SOURCE_PATH")
    source_path = Path(source_path_val) if source_path_val else None
    source_name = source_data.get("SOURCE_NAME", "my-theme")

    if source_path is None or not source_path.exists():
        print(
            f"Skipping source '{source_name}': "
            f"file not found at '{source_path_val}'")
        return

    print(f"\n{'='*60}")
    print(f"Processing source: '{source_name}' ({source_path.name})")
    print(f"{'='*60}")

    pattern = re.compile(
        r"/\*\s*obsi-snip-coll\s+start(?::\s*([^ ]+))?"
        r"\s*\*/(.*?)/\*\s*obsi-snip-coll\s+end\s*\*/",
        re.DOTALL | re.IGNORECASE
    )

    try:
        content = source_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading source file: {e}")
        return

    filtered_lines_map = build_filtered_lines_map(content)
    matches = list(pattern.finditer(content))
    print(f"Found {len(matches)} snippet(s) in source file")

    existing_entries_for_source = {
        k: v for k, v in index.items()
        if k.startswith(f"{source_name}_{source_path.name}")
    }

    for match in matches:
        snippet_name_from_comment = match.group(1)
        css_content = match.group(2).strip()
        original_line_start = (
            content.count('\n', 0, match.start()) + 1)
        original_line_end = (
            content.count('\n', 0, match.end()) + 1)
        line_start = filtered_lines_map.get(original_line_start, 0)
        line_end = filtered_lines_map.get(original_line_end, 0)
        line_count_diff = line_end - line_start
        index_key = (
            f"{source_name}_{source_path.name}"
            f"_{line_start}_{line_end}")
        found_match_info: Dict[str, str] = {}

        print(
            f"\n--- Snippet (lines {line_start}-{line_end}) ---")
        if args.non_interactive:
            css_lines = css_content.split('\n')
            preview = css_lines[0] if css_lines else ''
            more = '...' if len(preview) > 80 else ''
            print(
                f"  {preview[:80]}{more} "
                f"({len(css_lines)} lines)")
        else:
            print(css_content)
        print("---------------------------------------")

        # Tier 1: Exact minified content match
        minified_css = minify_css(css_content)
        for existing_key, existing_path in (
                existing_entries_for_source.items()):
            try:
                existing_content = Path(existing_path).read_text(
                    encoding='utf-8')
                if minify_css(existing_content) == minified_css:
                    found_match_info = {
                        "key": existing_key, "action": "update"}
                    print(
                        f"  => Exact content match: "
                        f"{existing_key}")
                    break
            except FileNotFoundError:
                continue

        # Tier 2: Exact index key match
        if not found_match_info and index_key in index:
            found_match_info = {
                "key": index_key, "action": "update"}
            print(f"  => Exact key match: {index_key}")

        # Tier 3: Line count + proximity match
        if not found_match_info:
            for existing_key in existing_entries_for_source:
                (_, _, old_start,
                 old_end) = parse_index_key(existing_key)
                if old_start is None:
                    continue
                old_diff = old_end - old_start
                if line_count_diff == old_diff:
                    start_diff = abs(line_start - old_start)
                    if start_diff <= 30:
                        found_match_info = {
                            "key": existing_key,
                            "action": "update"}
                        print(
                            f"  => Proximity match "
                            f"({start_diff} lines away): "
                            f"{existing_key}")
                        break
                    else:
                        print(
                            f"  ? Weak match "
                            f"({start_diff} lines away): "
                            f"{existing_key}")
                        if args.yes:
                            found_match_info = {
                                "key": existing_key,
                                "action": "update"}
                            print("  => Auto-accepted (-y)")
                        elif args.non_interactive:
                            found_match_info = {
                                "action": "skip"}
                            print(
                                "  => Skipped (non-interactive)")
                        else:
                            choice = input(
                                "  Update this entry? "
                                "(y/N): ").strip().lower()
                            if choice in ('y', 'yes'):
                                found_match_info = {
                                    "key": existing_key,
                                    "action": "update"}
                            else:
                                found_match_info = {
                                    "action": "skip"}
                        break

        # Process the match result
        if found_match_info.get("action") == "update":
            found_key = found_match_info["key"]
            old_path = Path(index[found_key])
            snippet_name = old_path.stem

            # Look up metadata using file stem first, then
            # comment name as fallback, so renaming the source
            # comment tag does not lose the existing entry.
            meta_entry = metadata.get(
                source_name, {}).get(snippet_name, {})
            if not meta_entry and snippet_name_from_comment:
                meta_entry = metadata.get(
                    source_name, {}
                ).get(snippet_name_from_comment, {})

            description = (
                meta_entry.get("description", "")
                or f"Snippet extracted from {source_name}.")
            meta_subdir = meta_entry.get("sub_directory", "")

            # If metadata specifies a sub_directory, use it to
            # place the file there; otherwise keep current
            # location.
            target_subdir = meta_subdir or old_path.parent.name

            css_file_path = (
                Path("snippets") / source_name
                / target_subdir / f"{snippet_name}.css")
            md_file_path = css_file_path.with_suffix('.md')

            del index[found_key]
            index[index_key] = str(css_file_path)

            save_metadata_entry(
                metadata, source_name, snippet_name,
                target_subdir, description)

            write_css_and_md(
                css_content, css_file_path, md_file_path,
                source_name, source_data, snippet_name,
                description)
            stats["updated"] += 1

        elif found_match_info.get("action") == "skip":
            print("  -- Skipped")
            stats["skipped"] += 1
            continue

        # Tier 4: Scan all existing snippet files on disk for
        # content match. Catches cases where the index key is
        # stale (e.g. line numbers shifted) and the source
        # comment has no name tag, so metadata cannot be
        # looked up otherwise.
        if not found_match_info:
            snippet_scan_dir = Path("snippets") / source_name
            if snippet_scan_dir.exists():
                for css_file in sorted(
                        snippet_scan_dir.rglob("*.css")):
                    try:
                        blob = css_file.read_text(
                            encoding='utf-8')
                        if minify_css(blob) == minified_css:
                            for ek in list(index.keys()):
                                if Path(index[ek]) == css_file:
                                    found_match_info = {
                                        "key": ek,
                                        "action": "update"}
                                    print(
                                        f"  => On-disk content "
                                        f"match: {ek}")
                                    break
                            if found_match_info:
                                break
                    except Exception:
                        continue

        if not found_match_info:
            # No match found - create new snippet
            meta_entry = (
                metadata.get(source_name, {}).get(
                    snippet_name_from_comment)
                if snippet_name_from_comment else None)
            default_sub_directory = (
                meta_entry.get("sub_directory", "")
                if meta_entry else "uncategorized")
            default_description = (
                meta_entry.get("description", "")
                if meta_entry else "")
            default_name = (
                snippet_name_from_comment
                if snippet_name_from_comment else "")

            if args.non_interactive:
                snippet_name = (
                    default_name or f"snippet-{line_start}")
                sub_directory = (
                    default_sub_directory or "uncategorized")
                description = default_description or ""
            else:
                if snippet_name_from_comment and meta_entry:
                    print(
                        f"  Metadata found for "
                        f"'{snippet_name_from_comment}'")
                elif snippet_name_from_comment:
                    print(
                        f"  No metadata for "
                        f"'{snippet_name_from_comment}', "
                        f"prompting...")
                else:
                    print(
                        "  No snippet name in source, "
                        "prompting...")

                raw = input(
                    f"  Name [{default_name}]: ").strip()
                snippet_name = raw or default_name
                raw = input(
                    f"  Subdirectory "
                    f"[{default_sub_directory}]: ").strip()
                sub_directory = raw or default_sub_directory
                raw = input(
                    f"  Description "
                    f"[{default_description}]: ").strip()
                description = raw or default_description

            if not snippet_name:
                print("  -- Skipped (no name)")
                stats["skipped"] += 1
                continue

            save_metadata_entry(
                metadata, source_name, snippet_name,
                sub_directory, description)

            output_dir = (
                Path("snippets") / source_name / sub_directory)
            css_file_path = output_dir / f"{snippet_name}.css"
            md_file_path = css_file_path.with_suffix('.md')

            if write_css_and_md(
                css_content, css_file_path, md_file_path,
                source_name, source_data, snippet_name,
                description
            ):
                index[index_key] = str(css_file_path)
                stats["created"] += 1
            else:
                stats["skipped"] += 1


def main() -> None:
    """Entry point: parse args, load env/index/metadata, process all
    sources, save results."""
    args = parse_args()

    if args.validate:
        index = load_json(INDEX_FILE)
        metadata = load_json(METADATA_FILE)
        env_vars = load_env(args.env_path)
        sources = parse_sources(env_vars)
        issues = validate_metadata(metadata, index, sources)
        if issues:
            print(f"Found {len(issues)} issue(s):")
            for issue in issues:
                print(issue)
            sys.exit(1)
        else:
            print(
                "All metadata entries are consistent with "
                "existing files.")
        return

    print("CSS Snippet Extractor")
    print("=====================\n")

    env_vars = load_env(args.env_path)
    sources = parse_sources(env_vars)
    index = load_json(INDEX_FILE)
    metadata = load_json(METADATA_FILE)

    if not sources or sources[0].get("SOURCE_PATH") is None:
        print(
            "No sources found in .env. "
            "Please configure your source files.")
        return

    stats: Dict[str, int] = {
        "created": 0, "updated": 0, "skipped": 0}

    for source_data in sources:
        process_source(
            source_data, index, metadata, args, stats)

    save_json(INDEX_FILE, index)
    save_json(METADATA_FILE, metadata)

    total = stats["created"] + stats["updated"] + stats["skipped"]
    print(f"\n{'='*60}")
    print(
        f"Summary: {stats['created']} created, "
        f"{stats['updated']} updated, "
        f"{stats['skipped']} skipped ({total} total)")
    if stats['created'] + stats['updated'] > 0:
        print("Index and metadata files saved.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
