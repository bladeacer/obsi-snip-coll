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

    matches = pattern.finditer(content)
    snippets_found = 0

    for match in matches:
        snippets_found += 1
        css_content = match.group(1).strip()
        line_start = get_line_number(content, match.start())
        line_end = get_line_number(content, match.end())
        
        # Updated key format to include source name
        index_key = f"{source_name}_{source_path.name}_{line_start}_{line_end}"

        print(f"\n--- Snippet #{snippets_found} Preview (from lines {line_start}-{line_end}) ---")
        print(css_content)
        print("---------------------------------------")

        css_file_path = None
        
        # Check if the snippet already exists in the index
        if index_key in index:
            css_file_path = Path(index[index_key])
            print(f"This snippet is already indexed at '{css_file_path}'.")
            update_choice = input("Do you want to update it? (yes/no, default: no): ").strip().lower()
            if update_choice not in ['yes', 'y']:
                print("Skipping update.")
                continue

        # If not in the index or user chose to update, get new info
        if css_file_path is None:
            snippet_name = input("Enter a name for the snippet (e.g., 'dark-mode-toggle'): ").strip()
            sub_directory = input("Enter a subdirectory (e.g., 'custom-ui'): ").strip()
            output_dir = Path("snippets") / source_name / sub_directory
            output_dir.mkdir(parents=True, exist_ok=True)
            css_file_path = output_dir / f"{snippet_name}.css"
        else:
            snippet_name = css_file_path.stem
            
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

        # Construct the Markdown content with front matter
        md_file_path = css_file_path.with_suffix('.md')
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

