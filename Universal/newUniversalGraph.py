# To run this script:
# 1. First, generate the ASTs for a project using 'generate_asts_final.py'.
# 2. Use the corresponding advanced configuration file (e.g., python.graph.config.json).
# 3. Execute from your terminal:
#    python create_rich_dependency_graph.py ./PythonAST ./python.graph.config.json python_deps.dot

import json
import os
import sys
import re
from typing import Any, Dict, List, Optional

# --- Helper Functions ---

def get_config_value(config: Dict[str, Any], key_path: str, default_value: Any = None) -> Any:
    """Safely gets a value from a nested dictionary."""
    value = config
    for key in key_path.split('.'):
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default_value
    return value if value is not None else default_value

def find_nodes_by_type(node: Dict[str, Any], node_type: str) -> List[Dict[str, Any]]:
    """Recursively finds all nodes of a specific type in the AST."""
    nodes = []
    if not isinstance(node, dict): return nodes
    if node.get('type') == node_type:
        nodes.append(node)
    for child in node.get('children', []):
        nodes.extend(find_nodes_by_type(child, node_type))
    return nodes

def extract_value_by_path(node: Dict[str, Any], query: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extracts a text value from a node by following a path query."""
    if not query or not isinstance(node, dict): return None
    current_node = node
    for step in query.get('path', []):
        is_last_step = step == query['path'][-1]
        allowed_types = step.get('type')
        if is_last_step and not isinstance(allowed_types, list):
            allowed_types = [allowed_types]
        child_node = next((c for c in current_node.get('children', [])
                           if isinstance(c, dict) and (c.get('type') in allowed_types if is_last_step else c.get('type') == allowed_types) and
                           (not step.get('textMatch') or step.get('textMatch') in c.get('text', ''))), None)
        if not child_node: return None
        current_node = child_node
    return current_node.get('text', '').replace("'", "").replace('"', '')

# --- Core Graphing Logic ---

class DependencyGraph:
    """A class to build and manage the dependency graph."""
    def __init__(self):
        self.nodes = set()
        self.edges = set()

    def add_node(self, node_id: str, label: str, node_type: str):
        shape, color = "box", "black"
        if node_type == "file":
            shape, color = "ellipse", "lightblue"
        elif node_type == "folder":
            shape, color = "folder", "gray"
        elif node_type == "module":
            shape, color = "component", "orange"
        
        dot_node = f'  "{node_id}" [label="{label}", shape="{shape}", color="{color}", style=filled];'
        self.nodes.add(dot_node)

    def add_edge(self, source: str, target: str, label: str):
        dot_edge = f'  "{source}" -> "{target}" [label="{label}"];'
        self.edges.add(dot_edge)

    def add_folder_hierarchy(self, file_label: str):
        """Creates nodes for each part of a file's path and connects them."""
        parts = file_label.split("/")
        parent = None
        current_path = ""
        for part in parts[:-1]:
            current_path = f"{current_path}/{part}" if current_path else part
            self.add_node(current_path, part, "folder")
            if parent:
                self.add_edge(parent, current_path, "contains")
            parent = current_path
        if parent:
            self.add_edge(parent, file_label, "contains")

    def generate_dot_file(self, output_path: str):
        """Generates and saves the final .dot file."""
        dot_content = [
            "digraph G {",
            "  rankdir=LR;",
            "  node [fontname=\"Helvetica\"];",
            "  edge [fontname=\"Helvetica\"];",
            "\n  // --- Nodes ---",
            *sorted(list(self.nodes)),
            "\n  // --- Edges ---",
            *sorted(list(self.edges)),
            "}"
        ]
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(dot_content))
        print(f"\n✅ Successfully generated rich dependency graph at: {output_path}")

def main(ast_dir: str, config_path: str, output_path: str):
    """Main function to analyze a directory and generate the dependency graph."""
    if not os.path.isdir(ast_dir) or not os.path.isfile(config_path):
        print("Error: AST directory or language configuration not found.", file=sys.stderr)
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        lang_config = json.load(f)

    print(f"Generating dependency graph using '{lang_config.get('language')}' configuration...")

    graph = DependencyGraph()
    # Use the new external patterns for filtering
    external_patterns = [re.compile(p) for p in get_config_value(lang_config, 'externalDependencyPatterns', [])]
    import_selectors = get_config_value(lang_config, 'selectors.import', [])

    for root, _, files in os.walk(ast_dir):
        for file in files:
            if file.endswith('.json'):
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, ast_dir).replace("\\", "/")
                source_node_id = os.path.splitext(relative_path)[0]
                
                graph.add_node(source_node_id, os.path.basename(source_node_id), "file")
                graph.add_folder_hierarchy(source_node_id)

                try:
                    with open(full_path, 'r', encoding='utf-8') as f_ast:
                        ast_data = json.load(f_ast)
                    
                    for selector in import_selectors:
                        for node in find_nodes_by_type(ast_data, selector.get('type')):
                            import_path = extract_value_by_path(node, selector.get('source'))
                            if not import_path:
                                continue

                            # If the import is NOT external, we assume it's internal and graph it.
                            if not any(p.search(import_path) for p in external_patterns):
                                graph.add_node(import_path, import_path, "module")
                                graph.add_edge(source_node_id, import_path, "imports")
                                
                except Exception as e:
                    print(f"\n❌ Failed to analyze file: {full_path}. Reason: {e}", file=sys.stderr)

    graph.generate_dot_file(output_path)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python create_rich_dependency_graph.py <path-to-ast-directory> <path-to-config.json> [output_file.dot]")
    else:
        ast_directory = sys.argv[1]
        config_file_path = sys.argv[2]
        output_file = sys.argv[3] if len(sys.argv) > 3 else "dependencies.dot"
        main(ast_directory, config_file_path, output_file)