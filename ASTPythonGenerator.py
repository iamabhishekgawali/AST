# To run this script:
# 1. Install the necessary packages:
#    pip install tree-sitter tree-sitter-python
# 2. Execute it from your terminal, passing the path to the project you want to analyze:
#    python generate_python_ast.py /path/to/your/python/project

import json
import os
import sys
from tree_sitter import Language, Parser
# Import the specific language package.
import tree_sitter_python as tspython

def node_to_dict(node):
    """
    Recursively converts a tree-sitter node to a serializable dictionary,
    matching the structure of the JavaScript AST generator for consistency.
    """
    if not node:
        return None
        
    start_point = {'row': node.start_point[0], 'column': node.start_point[1]}
    end_point = {'row': node.end_point[0], 'column': node.end_point[1]}

    return {
        'type': node.type,
        'text': node.text.decode('utf8'),
        'startPosition': start_point,
        'endPosition': end_point,
        # Using named_children for a cleaner, more relevant AST, like in the JS script.
        'children': [node_to_dict(child) for child in node.named_children]
    }


def parse_and_save_asts(project_dir, output_dir, parser):
    """
    Recursively finds and parses all .py files in a project directory,
    saving each AST to a corresponding JSON file in the output directory.
    """
    file_count = 0
    ignored_dirs = {'__pycache__', '.git', '.venv', 'venv', 'env', 'dist', 'build', 'PythonAST'}
    
    # Also ignore this script itself if it's in the project directory
    script_name = os.path.basename(__file__)
    
    for root, dirs, files in os.walk(project_dir, topdown=True):
        # Exclude ignored directories from the search
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        
        for file_name in files:
            if file_name.endswith('.py') and file_name != script_name:
                file_path = os.path.join(root, file_name)
                
                try:
                    with open(file_path, 'rb') as f: # Read as bytes for tree-sitter
                        code_bytes = f.read()
                    
                    # Parse the code into an AST
                    tree = parser.parse(code_bytes)
                    
                    # Convert the AST to a serializable dictionary
                    serializable_ast = node_to_dict(tree.root_node)
                    
                    # Determine the output path for the AST JSON file
                    relative_path = os.path.relpath(file_path, project_dir)
                    output_file_path = os.path.join(output_dir, f"{relative_path}.json")
                    output_file_dir = os.path.dirname(output_file_path)
                    
                    # Ensure the output directory for this file exists
                    os.makedirs(output_file_dir, exist_ok=True)
                    
                    # Write the serializable AST to the JSON file
                    with open(output_file_path, 'w', encoding='utf-8') as f_json:
                        json.dump(serializable_ast, f_json, indent=2)
                    
                    print(f"[SUCCESS] Saved AST for: {file_path} -> {output_file_path}")
                    file_count += 1
                
                except Exception as e:
                    print(f"[FAILED] Could not process {file_path}. Reason: {e}")

    return file_count

# --- Main Execution ---
if __name__ == "__main__":
    print("Setting up Python AST parser...")
    
    # Initialize the Parser using the method confirmed to work in your environment.
    try:
        PY_LANGUAGE = Language(tspython.language())
        parser = Parser(PY_LANGUAGE)
        
    except Exception as e:
        print(f"Error: Could not initialize the Tree-sitter parser. Please ensure 'tree-sitter' and 'tree-sitter-python' are installed correctly.")
        print(f"Details: {e}")
        sys.exit(1)
        
    # Get project directory from command-line arguments
    if len(sys.argv) < 2:
        project_directory = "." # Default to current directory if none is provided
        print("Warning: No project directory provided. Defaulting to current directory.")
        print("Usage: python generate_python_ast.py <path-to-your-project>")
    else:
        project_directory = sys.argv[1]
    
    if not os.path.isdir(project_directory):
        print(f"\nError: The specified directory does not exist: '{project_directory}'")
        sys.exit(1)

    # Define the output directory
    output_directory = os.path.join(os.getcwd(), "PythonAST")
    
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
        
    print(f"\nStarting AST parsing for project at: '{os.path.abspath(project_directory)}'")
    print(f"AST files will be saved in: '{os.path.abspath(output_directory)}'\n")
    
    # Run the parsing and saving process
    total_files_parsed = parse_and_save_asts(project_directory, output_directory, parser)
    
    # Display a summary
    if total_files_parsed > 0:
        print(f"\n✅ Successfully generated and saved ASTs for {total_files_parsed} files.")
    else:
        print("\n⚠️ No Python files (.py) were found to parse in the specified directory.")
