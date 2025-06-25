import os
import json
from tree_sitter import Parser
import tree_sitter_python as tspython  # provides Python grammar

# Initialize the Tree-sitter parser for Python
parser = Parser()
parser.set_language(tspython.language())

def node_to_dict(node, source_code):
    """
    Recursively converts a Tree-sitter node to a JSON-serializable dictionary.
    """
    result = {
        'type': node.type,
        'start_point': node.start_point,  # (row, column)
        'end_point': node.end_point,
    }

    # If it's a leaf node, capture the raw code
    if len(node.children) == 0:
        result['text'] = source_code[node.start_byte:node.end_byte].decode('utf-8')
    else:
        result['children'] = [node_to_dict(child, source_code) for child in node.children]

    return result

def parse_python_file(file_path):
    """
    Parses a single Python file using Tree-sitter and returns its AST as a dictionary.
    """
    with open(file_path, 'rb') as f:
        source_code = f.read()
    tree = parser.parse(source_code)
    return node_to_dict(tree.root_node, source_code)

def parse_python_project(project_path, output_dir):
    """
    Parses all .py files in a directory using Tree-sitter and writes JSON ASTs to disk.
    """
    os.makedirs(output_dir, exist_ok=True)

    for root, dirs, files in os.walk(project_path):
        # Skip common directories
        for skip in ['venv', '__pycache__']:
            if skip in dirs:
                dirs.remove(skip)

        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)

                # Skip this script file itself
                if os.path.abspath(file_path) == os.path.abspath(__file__):
                    continue

                relative_path = os.path.relpath(file_path, project_path)
                output_file_path = os.path.join(output_dir, relative_path + '.json')
                os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

                try:
                    ast_dict = parse_python_file(file_path)

                    with open(output_file_path, 'w', encoding='utf-8') as out_f:
                        json.dump(ast_dict, out_f, indent=2)

                    print(f"[SUCCESS] Parsed: {file_path}")
                except Exception as e:
                    print(f"[ERROR] Failed to parse {file_path}: {e}")

if __name__ == "__main__":
    project_root = '.'  # current directory
    output_directory = './ast_output_tree_sitter'
    parse_python_project(project_root, output_directory)
    print("\n✅ Tree-sitter AST generation complete.")
