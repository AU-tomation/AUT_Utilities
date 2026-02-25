"""
generate_manifest.py
────────────────────
Esegui questo script UNA VOLTA dalla cartella radice della documentazione
(quella che contiene index.html, script.js, Tc3DocGenHtml.css):

    python generate_manifest.py

Genera un file manifest.json che index.html usa per costruire la sidebar
senza dover fare directory listing (che Python non restituisce quando
esiste un index.html).

Ri-eseguilo ogni volta che Beckhoff rigenera la documentazione.
"""

import os
import json

# Cartelle da escludere completamente
SKIP_FOLDERS = {'files'}

# Estensioni considerate pagine di documentazione
DOC_EXTENSIONS = {'.htm', '.html'}


def scan(folder_path, base_path):
    """
    Scansiona ricorsivamente folder_path e ritorna un nodo albero.

    Regola speciale: se una cartella ha lo stesso nome (case-insensitive) di un
    file HTM nella stessa cartella, i figli della cartella vengono "sollevati"
    come figli diretti del file HTM, eliminando il nodo-cartella intermedio.
    Esempio:
        StringBuilder.HTM  +  StringBuilder/   →  nodo StringBuilder.HTM
                                                     con figli Append, Reset, ...
    """
    name = os.path.basename(folder_path)
    node = {"name": name, "path": None, "children": []}

    try:
        entries = sorted(os.scandir(folder_path), key=lambda e: (e.is_dir(), e.name.lower()))
    except PermissionError:
        return node

    # Prima passata: raccogli file HTM e sottocartelle separatamente
    htm_files = {}   # name_lower -> file_node dict
    subdirs   = []   # (entry, child_node) da processare

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

    # Seconda passata: processa le sottocartelle
    for entry in subdirs:
        child = scan(entry.path, base_path)
        if not (child["children"] or child["path"]):
            continue  # cartella vuota, salta

        # Se esiste un HTM con lo stesso nome, solleva i figli sotto di esso
        key = entry.name.lower()
        if key in htm_files:
            htm_files[key]["children"].extend(child["children"])
        else:
            node["children"].append(child)

    return node


def find_prj_folder(base_path):
    """Trova la cartella *_PRJ nella base."""
    for entry in os.scandir(base_path):
        if entry.is_dir() and '_PRJ' in entry.name.upper():
            return entry.path
    # fallback: prima cartella non-skip
    for entry in os.scandir(base_path):
        if entry.is_dir() and entry.name not in SKIP_FOLDERS:
            return entry.path
    return None


def build_manifest(base_path):
    prj_path = find_prj_folder(base_path)
    if not prj_path:
        raise RuntimeError(f"Nessuna cartella *_PRJ trovata in: {base_path}")

    plc_path = os.path.join(prj_path, 'PLC')
    if not os.path.isdir(plc_path):
        raise RuntimeError(f"Cartella PLC non trovata in: {prj_path}")

    # Trova il file HTM anchor (es. AUT_Utilities.HTM) direttamente in PLC/
    anchor_file = None
    content_folder = None
    for entry in os.scandir(plc_path):
        if entry.is_file() and entry.name.lower().endswith('.htm'):
            anchor_file = entry
        elif entry.is_dir():
            content_folder = entry.path

    if not anchor_file:
        raise RuntimeError(f"Nessun file HTM trovato in: {plc_path}")

    anchor_rel = os.path.relpath(anchor_file.path, base_path).replace('\\', '/')
    anchor_name = os.path.splitext(anchor_file.name)[0]

    root = {
        "name": anchor_name,
        "path": anchor_rel,
        "isRoot": True,
        "children": []
    }

    if content_folder:
        # Scansiona ogni sottocartella di content_folder
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
                    "name": os.path.splitext(entry.name)[0],
                    "path": rel,
                    "children": []
                })

    return root


if __name__ == '__main__':
    base = os.path.dirname(os.path.abspath(__file__))
    print(f"Scansione da: {base}")

    try:
        manifest = build_manifest(base)
        out_path = os.path.join(base, 'manifest.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # Count pages
        def count_pages(node):
            n = 1 if node.get('path') else 0
            for c in node.get('children', []):
                n += count_pages(c)
            return n

        total = count_pages(manifest)
        print(f"OK manifest.json generato -- {total} pagine indicizzate.")
        print(f"   Avvia il server: python -m http.server 8080")
        print(f"   Poi apri:        http://localhost:8080/index.html")

    except Exception as e:
        print(f"ERRORE: {e}")
        raise