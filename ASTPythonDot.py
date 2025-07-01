import os
import json
import networkx as nx
from pathlib import Path

def collect_ast_files(directory):
    """Recursively collect all .json files under the given directory."""
    ast_files = {}
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".json"):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        ast = json.load(f)
                        relative_path = os.path.relpath(full_path, directory)
                        ast_files[relative_path] = ast
                except Exception as e:
                    print(f"Warning: Failed to parse {file}: {e}")
    return ast_files

def extract_imports(ast_json):
    """Extract 'from x.y import z' as (module_path, symbol)"""
    imports = set()

    for node in ast_json.get("children", []):
        if node.get("type") == "import_from_statement":
            module = None
            symbol = None
            for child in node.get("children", []):
                if child.get("type") == "dotted_name":
                    if not module:
                        module = child["text"].strip()
                    else:
                        symbol = child["text"].strip()
            if module and symbol:
                imports.add((module.replace(".", "/"), symbol))
            elif module:
                imports.add((module.replace(".", "/"), None))

    return imports

def extract_attribute_dependencies(ast_json):
    """Heuristic: 'self.db' means dependency on Models.DAO"""
    deps = set()

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "attribute":
                text = node.get("text", "")
                if "self.db" in text:
                    deps.add("Models/DAO")
            for child in node.get("children", []):
                walk(child)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(ast_json)
    return deps

def build_dependency_graph(ast_files):
    G = nx.DiGraph()

    for path, ast in ast_files.items():
        node = path.replace("\\", "/").replace(".py.json", "")
        G.add_node(node)

        # Import dependencies
        for module_path, symbol in extract_imports(ast):
            target = f"{module_path}/{symbol}" if symbol else module_path
            G.add_edge(node, target.replace(".py", ""))

        # Attribute dependencies
        for dep in extract_attribute_dependencies(ast):
            G.add_edge(node, dep.replace(".py", ""))

    return G

def save_dot_file(G, output_path):
    nx.drawing.nx_pydot.write_dot(G, output_path)
    print(f"DOT file written to: {output_path}")

# === Run ===
if __name__ == "__main__":
    ast_dir = "./PythonAST"
    output_dot = os.path.join(ast_dir, "dependency_graph.dot")

    ast_files = collect_ast_files(ast_dir)
    print(f"Discovered {len(ast_files)} AST files")

    graph = build_dependency_graph(ast_files)
    save_dot_file(graph, output_dot)
