# To run this script:
# 1. Install the necessary packages:
#    pip install tree-sitter tree-sitter-languages tree-sitter-c-sharp
#
# 2. Execute from your terminal with ONLY the project path:
#    python generate_asts_final.py /path/to/your/project

import json
import os
import sys
from tree_sitter import Parser
from tree_sitter_languages import get_language

# --- Language Configuration Map ---
# The 'output_dir' key is back to define the language-specific folder names.
LANGUAGE_CONFIG = {
    'python': {'extensions': ['.py'], 'output_dir': 'PythonAST'},
    'java': {'extensions': ['.java'], 'output_dir': 'JavaAST'},
    'javascript': {'extensions': ['.js', '.jsx'], 'output_dir': 'JavascriptAST'},
    'typescript': {'extensions': ['.ts'], 'output_dir': 'TypescriptAST'},
    'tsx': {'extensions': ['.tsx'], 'output_dir': 'TypescriptAST'},
    'go': {'extensions': ['.go'], 'output_dir': 'GoAST'},
    'c-sharp': {'extensions': ['.cs'], 'output_dir': 'CSharpAST'} # Added C# support
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

def discover_languages_and_files(project_dir, ignored_dirs):
    """Scan the project to find which files to parse and return a map of file_path -> extension."""
    files_to_parse = {}
    all_extensions = {ext for config in LANGUAGE_CONFIG.values() for ext in config['extensions']}
    for root, dirs, files in os.walk(project_dir, topdown=True):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            _, extension = os.path.splitext(file)
            if extension in all_extensions:
                full_path = os.path.join(root, file)
                files_to_parse[full_path] = extension
    return files_to_parse

def initialize_parsers(extensions_found: set) -> dict:
    """Initializes only the parsers needed for the found file types."""
    parsers = {}
    print("Initializing required parsers...")
    ext_to_lang_key = {ext: key for key, conf in LANGUAGE_CONFIG.items() for ext in conf['extensions']}
    languages_to_load = {ext_to_lang_key[ext] for ext in extensions_found if ext in ext_to_lang_key}

    for lang_key in languages_to_load:
        try:
            print(f"  - Loading grammar for: {lang_key}")
            # Note: tree-sitter-languages uses 'c-sharp' for the get_language key
            language = get_language(lang_key)
            parser = Parser()
            parser.set_language(language)
            for ext in LANGUAGE_CONFIG[lang_key]['extensions']:
                parsers[ext] = parser
        except Exception as e:
            # Add a check for the specific C# package name in the error message
            package_name = 'tree-sitter-c-sharp' if lang_key == 'c-sharp' else f'tree-sitter-{lang_key}'
            print(f"  ❌ Error: Could not initialize parser for '{lang_key}'. Is it supported and is '{package_name}' installed?")
            print(f"     Details: {e}")

    return parsers

def parse_project(project_dir, files_to_parse, parsers, mirrored_output_dir):
    """Parses all discovered files and saves the AST to BOTH output structures."""
    file_count = 0
    ext_to_lang_key = {ext: key for key, conf in LANGUAGE_CONFIG.items() for ext in conf['extensions']}

    for file_path, extension in files_to_parse.items():
        parser = parsers.get(extension)
        if not parser:
            print(f"[SKIPPED] No parser available for file: {file_path}")
            continue
        try:
            with open(file_path, 'rb') as f:
                tree = parser.parse(f.read())
            
            serializable_ast = node_to_dict(tree.root_node)
            json_string = json.dumps(serializable_ast, indent=2)
            
            relative_path = os.path.relpath(file_path, project_dir)
            
            # 1. Path for the mirrored directory
            mirrored_output_path = os.path.join(mirrored_output_dir, f"{relative_path}.json")
            
            # 2. Path for the language-specific directory
            lang_key = ext_to_lang_key[extension]
            lang_specific_dir_name = LANGUAGE_CONFIG[lang_key]['output_dir']
            lang_specific_dir = os.path.join(os.getcwd(), lang_specific_dir_name)
            lang_specific_output_path = os.path.join(lang_specific_dir, f"{relative_path}.json")
            
            # Write to both locations
            os.makedirs(os.path.dirname(mirrored_output_path), exist_ok=True)
            with open(mirrored_output_path, 'w', encoding='utf-8') as f:
                f.write(json_string)

            os.makedirs(os.path.dirname(lang_specific_output_path), exist_ok=True)
            with open(lang_specific_output_path, 'w', encoding='utf-8') as f:
                f.write(json_string)

            print(f"[SUCCESS] Saved AST for: {file_path}")
            file_count += 1
        except Exception as e:
            print(f"[FAILED] Could not process {file_path}. Reason: {e}")

    return file_count

# --- Main Execution ---
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_asts_final.py <path-to-project>")
        sys.exit(1)

    project_directory = sys.argv[1]
    if not os.path.isdir(project_directory):
        print(f"Error: The specified directory does not exist: '{project_directory}'")
        sys.exit(1)

    mirrored_output_directory = os.path.join(os.getcwd(), "Project_AST_Output")
    os.makedirs(mirrored_output_directory, exist_ok=True)

    ignored_dirs = {'__pycache__', '.git', '.venv', 'venv', 'env', 'dist', 'build', 'target', 'bin', 'node_modules', os.path.basename(mirrored_output_directory)}
    for lang_cfg in LANGUAGE_CONFIG.values():
        ignored_dirs.add(lang_cfg['output_dir'])

    print(f"Scanning project at '{os.path.abspath(project_directory)}' to discover languages...")
    files_to_parse = discover_languages_and_files(project_directory, ignored_dirs)

    if not files_to_parse:
        print("\n⚠️ No supported source code files were found to parse.")
        sys.exit(0)
    
    found_extensions = set(files_to_parse.values())
    print(f"Discovered file types: {', '.join(sorted(list(found_extensions)))}\n")

    parsers_by_extension = initialize_parsers(found_extensions)

    if not parsers_by_extension:
        print("\nCould not initialize any parsers. Please check for installation errors above.")
        sys.exit(1)

    print(f"\nStarting AST generation for all discovered files...")
    print(f"Output will be saved in TWO formats:")
    print(f"  1. A single mirrored structure inside: '{os.path.abspath(mirrored_output_directory)}'")
    print(f"  2. Separate language-specific folders (e.g., PythonAST/, CSharpAST/, etc.)\n")
    
    total_files_parsed = parse_project(project_directory, files_to_parse, parsers_by_extension, mirrored_output_directory)
    
    if total_files_parsed > 0:
        print(f"\n✅ Successfully generated and saved ASTs for {total_files_parsed} files.")
    else:
        print("\n⚠️ No supported files were parsed.")