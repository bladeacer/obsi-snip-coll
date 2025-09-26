#!/usr/bin/env python3
import os
import re
import json
from pathlib import Path
from ast import literal_eval
import shlex

# The path to the JSON index file
INDEX_FILE = Path("snippets/index.json")

def load_env(env_path=None):
    """
    Loads environment variables from a .env file, supporting single-line
    and multi-line values for complex structures like SOURCES.
    
    Returns:
        dict: A dictionary of key-value pairs from the .env file.
    """
    if env_path is None:
        env_path = Path('.env')

    env_vars = {}
    if not env_path.exists():
        return env_vars
    
    content = env_path.read_text(encoding='utf-8')

    # Regex to find the SOURCES list block, handling multiline content
    sources_match = re.search(r"SOURCES\s*=\s*(\[.*?\])", content, re.DOTALL)
    
    if sources_match:
        env_vars['SOURCES'] = sources_match.group(1).strip()
    
    # Handle single-line key=value pairs
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line and not line.startswith('SOURCES'):
            key, value = line.split('=', 1)
            env_vars[key.strip()] = value.strip().strip('\'" ')
            
    return env_vars

def parse_sources(env_vars):
    """
    Parses the SOURCES variable from .env, supporting a list of dictionaries
    or falling back to a single source.
    
    Returns:
        list: A list of dictionaries, each representing a source.
    """
    sources_str = env_vars.get("SOURCES")
    if sources_str:
        try:
            parsed_sources = literal_eval(sources_str)
            
            # Check if it's a valid list of dictionaries
            if isinstance(parsed_sources, list) and all(isinstance(item, dict) for item in parsed_sources):
                return parsed_sources
            else:
                raise ValueError("Unsupported SOURCES format. Expected a list of dictionaries.")
        except (ValueError, SyntaxError) as e:
            print(f"Warning: Could not parse SOURCES from .env. Falling back to single source format. Error: {e}")
            pass # Fall through to single source
    
    # Fallback to the old single-source format
    return [{
        "SOURCE_PATH": env_vars.get("SOURCE_PATH"),
        "SOURCE_NAME": env_vars.get("SOURCE_NAME"),
        "AUTHOR": env_vars.get("AUTHOR"),
        "LICENSE": env_vars.get("LICENSE"),
        "REPO_URL": env_vars.get("REPO_URL"),
    }]


def load_index():
    """Loads the JSON index file, returning an empty dict if not found or corrupted."""
    if not INDEX_FILE.exists():
        return {}
    try:
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_index(index_data):
    """Saves the JSON index file."""
    try:
        INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2)
    except Exception as e:
        print(f"Error saving index file: {e}")

def get_line_number(text, index):
    """Returns the 1-based line number for a given character index."""
    return text.count('\n', 0, index) + 1

def build_filtered_lines_map(content):
    """
    Creates a mapping from original line numbers to "code-only" line numbers,
    ignoring comments and blank lines.
    """
    filtered_lines_map = {}
    filtered_line_counter = 0
    in_comment_block = False
    
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        stripped_line = line.strip()
        
        # Check for start of multiline comment
        if '/*' in stripped_line and '*/' not in stripped_line:
            in_comment_block = True
        
        # Check for end of multiline comment
        if '*/' in stripped_line and '/*' not in stripped_line:
            in_comment_block = False

        is_code_line = False
        if not in_comment_block and stripped_line:
            # Check for a single-line comment block
            if not stripped_line.startswith('/*') or not stripped_line.endswith('*/'):
                is_code_line = True
        
        if is_code_line:
            filtered_line_counter += 1
            
        filtered_lines_map[i] = filtered_line_counter

    return filtered_lines_map

def parse_index_key(key):
    """Parses a JSON index key to extract its components."""
    parts = key.rsplit('_', 3)
    if len(parts) == 4:
        source_name = parts[0]
        file_name = parts[1]
        try:
            line_start = int(parts[2])
            line_end = int(parts[3])
            return source_name, file_name, line_start, line_end
        except (ValueError, IndexError):
            pass
    return None, None, None, None

def get_description_from_markdown(md_path):
    """Reads a markdown file and extracts the description section."""
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Regex to find the description section after the front matter
            desc_match = re.search(r'---\s*\n(.*?)\s*---\s*\n.*?#.*?\n(.*?)(?=\n\[View this file\])', content, re.DOTALL)
            if desc_match:
                return desc_match.group(2).strip()
    except (FileNotFoundError, IndexError):
        pass
    return ""

def process_source(source_data, index):
    """Processes a single source file, extracting and saving snippets."""
    source_path_val = source_data.get("SOURCE_PATH")
    source_path = Path(source_path_val) if source_path_val else None
    
    source_name = source_data.get("SOURCE_NAME", "my-theme")
    author_name = source_data.get("AUTHOR", "Unknown Author")
    license_name = source_data.get("LICENSE", "MIT")
    repo_url = source_data.get("REPO_URL", "")
    
    if source_path is None or not source_path.exists():
        print(f"Skipping source '{source_name}': file not found at '{source_path_val}'")
        return

    print(f"\n--- Processing Source: '{source_name}' ---")

    # Regex to find CSS content between start and end comments
    pattern = re.compile(
        r"/\*\s*obsi-snip-coll\s+start.*?\*/(.*?)/\*\s*obsi-snip-coll\s+end\s*\*/",
        re.DOTALL | re.IGNORECASE
    )

    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading source file: {e}")
        return

    # Build the mapping of original line numbers to filtered line numbers
    filtered_lines_map = build_filtered_lines_map(content)

    matches = pattern.finditer(content)
    snippets_found = 0

    # Filter existing index entries for this specific source
    existing_entries_for_source = {
        k: v for k, v in index.items()
        if k.startswith(f"{source_name}_{source_path.name}")
    }

    for match in matches:
        snippets_found += 1
        css_content = match.group(1).strip()
        original_line_start = content.count('\n', 0, match.start()) + 1
        original_line_end = content.count('\n', 0, match.end()) + 1
        
        # Use the map to get the filtered line numbers
        line_start = filtered_lines_map.get(original_line_start, 0)
        line_end = filtered_lines_map.get(original_line_end, 0)
        line_count_diff = line_end - line_start

        index_key = f"{source_name}_{source_path.name}_{line_start}_{line_end}"
        found_match_key = None
        
        print(f"\n--- Snippet #{snippets_found} Preview (from lines {line_start}-{line_end}) ---")
        print(css_content)
        print("---------------------------------------")

        # --- New Logic for Duplicate Detection ---
        
        # First, check for an exact match (this handles updates after re-running the script)
        if index_key in index:
            found_match_key = index_key
        else:
            # If no exact match, search for a similar entry by line count difference
            for existing_key, existing_path in existing_entries_for_source.items():
                _, _, old_line_start, old_line_end = parse_index_key(existing_key)
                if old_line_start is None:
                    continue
                old_line_count_diff = old_line_end - old_line_start
                
                if line_count_diff == old_line_count_diff:
                    # Found a match by line count, now check line number proximity
                    line_start_diff = abs(line_start - old_line_start)
                    
                    if line_start_diff <= 30:
                        # Strong match: update automatically
                        found_match_key = existing_key
                        print(f"Found a strong match ({line_start_diff} lines away). Updating automatically...")
                        break
                    else:
                        # Weak match: prompt user
                        print(f"Found a weak match by line count ({line_start_diff} lines away) at {existing_key}.")
                        update_choice = input("Do you want to update this entry? (yes/no, default: no): ").strip().lower()
                        if update_choice in ['yes', 'y']:
                            found_match_key = existing_key
                        break
        
        if found_match_key:
            css_file_path = Path(index[found_match_key])
            md_file_path = css_file_path.with_suffix('.md')
            
            # Reconstruct metadata from existing files
            snippet_name = css_file_path.stem
            # We don't need to read the description since we are not rewriting the MD file.
            
            # Delete old entry from index and add new one with updated key
            del index[found_match_key]
            index[index_key] = str(css_file_path)
            
            print(f"Reusing existing paths: {css_file_path.parent}")
            
        else:
            # New entry - prompt for all info
            snippet_name = input("Enter a name for the snippet (e.g., 'dark-mode-toggle'): ").strip()
            sub_directory = input("Enter a subdirectory (e.g., 'custom-ui'): ").strip()
            output_dir = Path("snippets") / source_name / sub_directory
            output_dir.mkdir(parents=True, exist_ok=True)
            css_file_path = output_dir / f"{snippet_name}.css"
            md_file_path = css_file_path.with_suffix('.md')
            description = input("Enter a brief description for this snippet (optional): ").strip()
            
            if not snippet_name:
                print("Skipping this snippet as no name was provided.")
                continue

        # Save the CSS content
        try:
            with open(css_file_path, 'w', encoding='utf-8') as f:
                f.write(css_content)
            print(f"Saved CSS to '{css_file_path}'")
        except Exception as e:
            print(f"Error writing CSS file: {e}")

        # Conditionally write the Markdown file
        if not found_match_key:
            # Only write the Markdown file if it's a brand new entry
            markdown_content = f"""\
---
author: {author_name}
source: {repo_url}
license: {license_name}
---

# {snippet_name.replace('-', ' ').title()}

{description}

This snippet was automatically extracted from the `{source_name}` theme.

[View this file](./{css_file_path.name})
"""
            try:
                with open(md_file_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                print(f"Saved Markdown description to '{md_file_path}'")
            except Exception as e:
                print(f"Error writing Markdown file: {e}")

        # Update the index with the saved path
        index[index_key] = str(css_file_path)

    if snippets_found == 0:
        print(f"No snippets found in '{source_name}'.")
    else:
        print(f"Successfully processed {snippets_found} snippet(s) from '{source_name}'.")

def extract_and_save_snippets():
    """
    An interactive CLI to extract CSS snippets from a theme file,
    with defaults loaded from a .env file.
    """
    print("Welcome to the CSS Snippet Extractor CLI!\n")
    
    env_vars = load_env()
    sources = parse_sources(env_vars)
    index = load_index()
    
    if not sources or sources[0].get("SOURCE_PATH") is None:
        print("No sources found in .env. Please configure your source files.")
        return

    for source_data in sources:
        process_source(source_data, index)
    
    save_index(index)
    print("\nAll processing complete. Index file updated.")

if __name__ == "__main__":
    extract_and_save_snippets()

