# To run this script:
# 1. Install all desired language packages:
#    pip install tree-sitter tree-sitter-python tree-sitter-java tree-sitter-javascript tree-sitter-go tree-sitter-typescript
#
# 2. Execute from your terminal with ONLY the project path:
#    python generate_asts_fully_automated.py /path/to/your/project

import json
import os
import sys
import importlib
from tree_sitter import Language, Parser

# --- Source of Truth: The Full Language Configuration ---
# Maps language keys to their specific settings. The script uses this to know what to do.
LANGUAGE_CONFIG = {
    'python': {
        'import_name': 'tree_sitter_python',
        'extensions': ['.py'],
        'output_dir': 'PythonAST'
    },
    'java': {
        'import_name': 'tree_sitter_java',
        'extensions': ['.java'],
        'output_dir': 'JavaAST'
    },
    'javascript': {
        'import_name': 'tree_sitter_javascript',
        'extensions': ['.js', '.jsx'],
        'output_dir': 'JavascriptAST'
    },
    'typescript': {
        'import_name': 'tree_sitter_typescript',
        'extensions': ['.ts', '.tsx'],
        'output_dir': 'TypescriptAST'
    },
    'go': {
        'import_name': 'tree_sitter_go',
        'extensions': ['.go'],
        'output_dir': 'GoAST'
    }
}

def node_to_dict(node):
    """Recursively converts a tree-sitter node to a serializable dictionary."""
    if not node: return None
    start_point = {'row': node.start_point[0], 'column': node.start_point[1]}
    end_point = {'row': node.end_point[0], 'column': node.end_point[1]}
    return {
        'type': node.type,
        'text': node.text.decode('utf8'),
        'startPosition': start_point,
        'endPosition': end_point,
        'children': [node_to_dict(child) for child in node.named_children]
    }

def discover_languages(project_dir, ignored_dirs):
    """Scan the project to find which languages and file extensions are present."""
    found_extensions = set()
    for root, dirs, files in os.walk(project_dir, topdown=True):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            _, extension = os.path.splitext(file)
            if extension:
                found_extensions.add(extension)

    languages_to_load = set()
    for lang, config in LANGUAGE_CONFIG.items():
        if any(ext in found_extensions for ext in config['extensions']):
            languages_to_load.add(lang)
            
    return languages_to_load

def initialize_parsers(languages_to_load: set) -> dict:
    """Initializes and returns a dictionary of parsers mapped by file extension."""
    parsers = {}
    print("Initializing required parsers...")
    for lang_key in languages_to_load:
        config = LANGUAGE_CONFIG[lang_key]
        lang_import_name = config['import_name']
        output_dir = os.path.join(os.getcwd(), config['output_dir'])
        os.makedirs(output_dir, exist_ok=True) # Ensure output dir exists

        try:
            lang_module = importlib.import_module(lang_import_name)
            print(f"  - Loading grammar for: {lang_key} (extensions: {', '.join(config['extensions'])})")
            
            # Special handling for typescript which has multiple grammar entry points
            if lang_key == 'typescript':
                ts_parser = Parser(Language(lang_module.language_typescript()))
                tsx_parser = Parser(Language(lang_module.language_tsx()))
                parsers['.ts'] = {'parser': ts_parser, 'output_dir': output_dir}
                parsers['.tsx'] = {'parser': tsx_parser, 'output_dir': output_dir}
            else:
                parser = Parser(Language(lang_module.language()))
                for ext in config['extensions']:
                    parsers[ext] = {'parser': parser, 'output_dir': output_dir}
        except (ImportError, Exception) as e:
            print(f"  ❌ Error: Could not initialize parser for '{lang_key}'.")
            print(f"     Please ensure '{lang_import_name}' is installed ('pip install {lang_import_name}').")
    return parsers

def parse_project(project_dir, parsers, ignored_dirs):
    """Recursively finds and parses all relevant source files using the correct parser."""
    file_count = 0
    script_name = os.path.basename(__file__)
    supported_extensions = tuple(parsers.keys())

    for root, dirs, files in os.walk(project_dir, topdown=True):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file_name in files:
            if file_name.endswith(supported_extensions) and file_name != script_name:
                _, extension = os.path.splitext(file_name)
                parser_info = parsers.get(extension)
                if not parser_info: continue

                file_path = os.path.join(root, file_name)
                try:
                    with open(file_path, 'rb') as f:
                        tree = parser_info['parser'].parse(f.read())
                    
                    serializable_ast = node_to_dict(tree.root_node)
                    
                    relative_path = os.path.relpath(file_path, project_dir)
                    output_file_path = os.path.join(parser_info['output_dir'], f"{relative_path}.json")
                    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
                    
                    with open(output_file_path, 'w', encoding='utf-8') as f_json:
                        json.dump(serializable_ast, f_json, indent=2)
                    
                    print(f"[SUCCESS] Saved AST for: {file_path}")
                    file_count += 1
                except Exception as e:
                    print(f"[FAILED] Could not process {file_path}. Reason: {e}")

    return file_count

# --- Main Execution ---
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_asts_fully_automated.py <path-to-project>")
        sys.exit(1)

    project_directory = sys.argv[1]
    if not os.path.isdir(project_directory):
        print(f"Error: The specified directory does not exist: '{project_directory}'")
        sys.exit(1)

    # Define directories to ignore during discovery and parsing
    ignored_dirs = {'__pycache__', '.git', '.venv', 'venv', 'env', 'dist', 'build', 'target', 'bin', 'node_modules'}
    for lang_cfg in LANGUAGE_CONFIG.values():
        ignored_dirs.add(lang_cfg['output_dir'])

    # 1. Discover which languages are in the project
    print(f"Scanning project at '{os.path.abspath(project_directory)}' to discover languages...")
    languages_found = discover_languages(project_directory, ignored_dirs)

    if not languages_found:
        print("\n⚠️ No supported source code files were found to parse.")
        sys.exit(0)
    
    print(f"Discovered languages: {', '.join(sorted(list(languages_found)))}\n")

    # 2. Initialize only the parsers for the languages we found
    parsers_by_extension = initialize_parsers(languages_found)

    if not parsers_by_extension:
        print("\nCould not initialize any parsers. Please check for installation errors above.")
        sys.exit(1)

    # 3. Parse the entire project using the loaded parsers
    print(f"\nStarting AST generation for all discovered languages...\n")
    total_files_parsed = parse_project(project_directory, parsers_by_extension, ignored_dirs)
    
    # 4. Display a summary
    if total_files_parsed > 0:
        print(f"\n✅ Successfully generated and saved ASTs for {total_files_parsed} files.")
    else:
        print("\n⚠️ No supported files were parsed.")