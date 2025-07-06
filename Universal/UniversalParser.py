# To run this script:
# 1. Generate ASTs for any language.
# 2. Use the corresponding advanced configuration file.
# 3. Execute from your terminal:
#    python universal_ast_analyzer.py ./JavascriptAST ./javascript.advanced.config.json
#    python universal_ast_analyzer.py ./PythonAST ./python.advanced.config.json

import os
import sys
import json
import re
from typing import Any, Dict, List, Optional

# --- Helper Functions ---

def get_config_value(config: Dict[str, Any], key_path: str, default_value: Any = None) -> Any:
    """
    Safely gets a value from the language configuration dictionary.
    """
    keys = key_path.split('.')
    value = config
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default_value
    return value if value is not None else default_value

def find_nodes_by_type(node: Dict[str, Any], node_type: str) -> List[Dict[str, Any]]:
    """
    Traverses the AST to find all nodes of a specific type.
    """
    nodes = []
    if not node:
        return nodes
    if node.get('type') == node_type:
        nodes.append(node)
    
    if 'children' in node and isinstance(node['children'], list):
        for child in node['children']:
            nodes.extend(find_nodes_by_type(child, node_type))
    return nodes

def extract_value_by_path(node: Dict[str, Any], query: Dict[str, Any]) -> Optional[str]:
    """
    Extracts a specific value from a node by following a path query from the config.
    """
    if not query or not node:
        return None
    
    current_node = node
    for step in query.get('path', []):
        child_node = next((c for c in current_node.get('children', []) 
                           if c.get('type') == step.get('type') and 
                           (not step.get('textMatch') or step.get('textMatch') in c.get('text', ''))), 
                          None)
        if not child_node:
            return None
        current_node = child_node
        
    return current_node.get('text', '').replace("'", "").replace('"', '')

def analyze_ast_file(file_path: str, stats: Dict[str, Any], lang_config: Dict[str, Any]):
    """
    Analyzes a single AST file and aggregates statistics.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        json_content = f.read()
    
    if not json_content:
        return  # Skip empty files

    ast = json.loads(json_content)
    if not ast or 'type' not in ast:
        return # Skip invalid JSON

    # --- 1. Code Composition ---
    stats['composition']['fileCount'] += 1
    if ast.get('startPosition') and ast.get('endPosition'):
        stats['composition']['totalLinesOfCode'] += ast['endPosition']['row'] - ast['startPosition']['row'] + 1

    function_types = get_config_value(lang_config, 'selectors.function', [])
    for f_type in function_types:
        stats['composition']['functionCount'] += len(find_nodes_by_type(ast, f_type))

    class_types = get_config_value(lang_config, 'selectors.class', [])
    for c_type in class_types:
        stats['composition']['classCount'] += len(find_nodes_by_type(ast, c_type))

    comment_types = get_config_value(lang_config, 'selectors.comment', [])
    for c_type in comment_types:
        stats['composition']['totalComments'] += len(find_nodes_by_type(ast, c_type))

    # --- 2. Dependency Analysis ---
    import_selectors = get_config_value(lang_config, 'selectors.import', [])
    for selector in import_selectors:
        import_nodes = find_nodes_by_type(ast, selector.get('type'))
        for node in import_nodes:
            stats['dependencies']['importCount'] += 1
            dep_name = extract_value_by_path(node, selector.get('source'))
            if dep_name:
                stats['dependencies']['importFrequency'][dep_name] = stats['dependencies']['importFrequency'].get(dep_name, 0) + 1
    
    # --- 3. API, Database, and other Pattern-based Metrics ---
    pattern_selectors = get_config_value(lang_config, 'selectors.patterns', {})
    for metric_name, selector in pattern_selectors.items():
        nodes = find_nodes_by_type(ast, selector.get('type'))
        for node in nodes:
            if node.get('text') and selector.get('textMatch') in node.get('text', ''):
                if metric_name not in stats['usage']:
                    stats['usage'][metric_name] = {'count': 0, 'list': []}
                stats['usage'][metric_name]['count'] += 1
                value = extract_value_by_path(node, selector.get('value'))
                if value:
                    stats['usage'][metric_name]['list'].append(value)

def save_report_as_json(stats: Dict[str, Any], lang_config: Dict[str, Any]):
    """
    Saves the final statistics report to a JSON file.
    """
    all_dependencies = stats['dependencies']['importFrequency'].keys()
    internal_patterns = [re.compile(p) for p in get_config_value(lang_config, 'internalDependencyPatterns', [])]
    
    direct_dependencies = [dep for dep in all_dependencies if not any(p.search(dep) for p in internal_patterns)]
    
    report = {
        "Code Composition": stats['composition'],
        "Dependency Analysis": {
            "Number of import statements": stats['dependencies']['importCount'],
            "List of direct dependencies": direct_dependencies,
            "Import frequency by module/library": stats['dependencies']['importFrequency']
        },
        "API and Service Usage": {},
        "Framework & Infrastructure": {}
    }

    for metric_name, usage_data in stats.get('usage', {}).items():
        report["API and Service Usage"][metric_name] = usage_data

    dependency_maps = get_config_value(lang_config, 'dependencyMaps', {})
    for map_type, dep_map in dependency_maps.items():
        detected = [tech for lib, tech in dep_map.items() if lib in stats['dependencies']['importFrequency']]
        report["Framework & Infrastructure"][map_type] = detected

    output_file_path = os.path.join(os.getcwd(), 'analysis_report.json')
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n Successfully saved analysis report to: {output_file_path}")

def main(ast_dir: str, config_path: str):

    if not os.path.exists(ast_dir) or not os.path.exists(config_path):
        print("Error: AST directory or language configuration not found.", file=sys.stderr)
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        lang_config = json.load(f)
    
    print(f"Analyzing project with \"{lang_config.get('language')}\" configuration...")

    stats = {
        'composition': {'fileCount': 0, 'functionCount': 0, 'classCount': 0, 'totalLinesOfCode': 0, 'totalComments': 0},
        'dependencies': {'importCount': 0, 'importFrequency': {}},
        'usage': {}
    }

    for root, _, files in os.walk(ast_dir):
        for file in files:
            if file.endswith('.json'):
                full_path = os.path.join(root, file)
                try:
                    analyze_ast_file(full_path, stats, lang_config)
                except Exception as e:
                    print(f"\n❌ Failed to analyze file: {full_path}. Reason: {e}", file=sys.stderr)
    
    save_report_as_json(stats, lang_config)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python universal_ast_analyzer.py <path-to-ast-directory> <path-to-config.json>")
    else:
        ast_directory = sys.argv[1]
        config_file_path = sys.argv[2]
        main(ast_directory, config_file_path)