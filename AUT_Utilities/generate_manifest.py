"""
generate_manifest.py
────────────────────
Run this script ONCE from the documentation root folder
(the one containing index.html, script.js, Tc3DocGenHtml.css):

    python generate_manifest.py

Generates a manifest.json file that index.html uses to build the sidebar
without needing directory listing (which Python does not serve when
an index.html file is present).

Re-run it every time Beckhoff regenerates the documentation.
"""

import os
import json

# Folders to skip entirely
SKIP_FOLDERS = {'files'}

# File extensions treated as documentation pages
DOC_EXTENSIONS = {'.htm', '.html'}


def scan(folder_path, base_path):
    """
    Recursively scans folder_path and returns a tree node.

    Special rule: if a folder has the same name (case-insensitive) as an HTM
    file in the same folder, the folder's children are "lifted" as direct
    children of the HTM file node, removing the intermediate folder node.
    Example:
        StringBuilder.HTM  +  StringBuilder/   →  node StringBuilder.HTM
                                                     with children Append, Reset, ...
    """
    name = os.path.basename(folder_path)
    node = {"name": name, "path": None, "children": []}

    try:
        entries = sorted(os.scandir(folder_path), key=lambda e: (e.is_dir(), e.name.lower()))
    except PermissionError:
        return node

    # First pass: collect HTM files and subdirectories separately
    htm_files = {}   # name_lower -> file_node dict
    subdirs   = []   # entries to process

    for entry in entries:
        if entry.name.startswith('.'):
            continue

        if entry.is_file():
            ext = os.path.splitext(entry.name)[1].lower()
            if ext in DOC_EXTENSIONS:
                rel = os.path.relpath(entry.path, base_path).replace('\\', '/')
                stem = os.path.splitext(entry.name)[0]
                file_node = {"name": stem, "path": rel, "children": []}
                htm_files[stem.lower()] = file_node
                node["children"].append(file_node)

        elif entry.is_dir():
            if entry.name not in SKIP_FOLDERS:
                subdirs.append(entry)

    # Second pass: process subdirectories
    for entry in subdirs:
        child = scan(entry.path, base_path)
        if not (child["children"] or child["path"]):
            continue  # empty folder, skip

        # If an HTM file with the same name exists, lift children under it
        key = entry.name.lower()
        if key in htm_files:
            htm_files[key]["children"].extend(child["children"])
        else:
            node["children"].append(child)

    return node


def find_prj_folder(base_path):
    """Finds the *_PRJ folder under base_path."""
    for entry in os.scandir(base_path):
        if entry.is_dir() and '_PRJ' in entry.name.upper():
            return entry.path
    # Fallback: first non-skipped folder
    for entry in os.scandir(base_path):
        if entry.is_dir() and entry.name not in SKIP_FOLDERS:
            return entry.path
    return None


def build_manifest(base_path):
    prj_path = find_prj_folder(base_path)
    if not prj_path:
        raise RuntimeError(f"No *_PRJ folder found in: {base_path}")

    plc_path = os.path.join(prj_path, 'PLC')
    if not os.path.isdir(plc_path):
        raise RuntimeError(f"PLC folder not found in: {prj_path}")

    # Find the HTM anchor file (e.g. AUT_Utilities.HTM) directly under PLC/
    anchor_file    = None
    content_folder = None
    for entry in os.scandir(plc_path):
        if entry.is_file() and entry.name.lower().endswith('.htm'):
            anchor_file = entry
        elif entry.is_dir():
            content_folder = entry.path

    if not anchor_file:
        raise RuntimeError(f"No HTM file found in: {plc_path}")

    anchor_rel  = os.path.relpath(anchor_file.path, base_path).replace('\\', '/')
    anchor_name = os.path.splitext(anchor_file.name)[0]

    root = {
        "name":     anchor_name,
        "path":     anchor_rel,
        "isRoot":   True,
        "children": []
    }

    if content_folder:
        # Scan each subfolder of content_folder
        try:
            entries = sorted(os.scandir(content_folder), key=lambda e: (e.is_dir(), e.name.lower()))
        except PermissionError:
            entries = []

        for entry in entries:
            if entry.name.startswith('.'):
                continue
            if entry.is_dir() and entry.name not in SKIP_FOLDERS:
                child = scan(entry.path, base_path)
                if child["children"]:
                    root["children"].append(child)
            elif entry.is_file() and entry.name.lower().endswith('.htm'):
                rel = os.path.relpath(entry.path, base_path).replace('\\', '/')
                root["children"].append({
                    "name":     os.path.splitext(entry.name)[0],
                    "path":     rel,
                    "children": []
                })

    return root


if __name__ == '__main__':
    base = os.path.dirname(os.path.abspath(__file__))
    print(f"Scanning from: {base}")

    try:
        manifest = build_manifest(base)
        out_path = os.path.join(base, 'manifest.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        def count_pages(node):
            n = 1 if node.get('path') else 0
            for c in node.get('children', []):
                n += count_pages(c)
            return n

        total = count_pages(manifest)
        print(f"OK manifest.json generated — {total} pages indexed.")
        print(f"   Start the server: python -m http.server 8080")
        print(f"   Then open:        http://localhost:8080/index.html")

    except Exception as e:
        print(f"ERROR: {e}")
        raise