# To run this script:
# 1. First, generate the ASTs for a project using 'generate_asts_final.py'.
# 2. You will need a language configuration file (e.g., python.config.json).
# 3. Execute from your terminal:
#    python UniversalParser.py ./PythonAST ./python.config.json

import json
import os
import sys
import re
from typing import Any, Dict, List, Optional, Set

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
                           (not step.get('textMatch') or step.get('textMatch') in c.get('text', ''))),
                          None)

        if not child_node: return None
        current_node = child_node
        
    return current_node.get('text', '').replace("'", "").replace('"', '')

# --- Main Analysis Logic ---

def analyze_ast_file(ast: Dict[str, Any], stats: Dict[str, Any], lang_config: Dict[str, Any]):
    """Analyzes a single AST file and aggregates statistics."""
    if not ast or not isinstance(ast, dict): return

    # Composition Metrics
    stats['composition']['fileCount'] += 1
    if ast.get('startPosition') and ast.get('endPosition'):
        stats['composition']['totalLinesOfCode'] += ast['endPosition']['row'] - ast['startPosition']['row'] + 1
    
    function_nodes = []
    for f_type in get_config_value(lang_config, 'selectors.function', []):
        function_nodes.extend(find_nodes_by_type(ast, f_type))
    stats['composition']['functionCount'] += len(function_nodes)

    for c_type in get_config_value(lang_config, 'selectors.class', []):
        stats['composition']['classCount'] += len(find_nodes_by_type(ast, c_type))

    for c_type in get_config_value(lang_config, 'selectors.comment', []):
        stats['composition']['totalComments'] += len(find_nodes_by_type(ast, c_type))

    # Dependency Analysis
    for selector in get_config_value(lang_config, 'selectors.import', []):
        for node in find_nodes_by_type(ast, selector.get('type')):
            stats['dependencies']['importCount'] += 1
            dep_name = extract_value_by_path(node, selector.get('source'))
            if dep_name:
                stats['dependencies']['importFrequency'][dep_name] = stats['dependencies']['importFrequency'].get(dep_name, 0) + 1

    # Enhanced Pattern-based Metrics
    for metric, patterns in get_config_value(lang_config, 'selectors.patterns', {}).items():
        if not isinstance(patterns, list):
            patterns = [patterns]
        
        for selector in patterns:
            for node in find_nodes_by_type(ast, selector.get('type')):
                if selector.get('textMatch') in node.get('text', ''):
                    stats['patterns'][metric]['count'] += 1
                    value = extract_value_by_path(node, selector.get('value'))
                    if value:
                        stats['patterns'][metric]['list'].add(value)
    
    # Quality and Complexity
    for t_type in get_config_value(lang_config, 'selectors.quality.exceptionHandling', []):
        stats['quality']['tryCatchCount'] += len(find_nodes_by_type(ast, t_type))

    complexity_rules = get_config_value(lang_config, 'selectors.cyclomaticComplexity', {})
    branch_nodes = complexity_rules.get('branchingNodes', [])
    for func_node in function_nodes:
        complexity = 1
        for b_node_type in branch_nodes:
            complexity += len(find_nodes_by_type(func_node, b_node_type))
        stats['complexity']['totalCyclomatic'] += complexity


def finalize_report(stats: Dict[str, Any], lang_config: Dict[str, Any]) -> Dict[str, Any]:
    """Assembles the final report from the aggregated statistics."""
    
    # Finalize dependencies
    all_deps = stats['dependencies']['importFrequency']
    internal_patterns = [re.compile(p) for p in get_config_value(lang_config, 'internalDependencyPatterns', [])]
    direct_deps = {dep: count for dep, count in all_deps.items() if not any(p.search(dep) for p in internal_patterns)}
    
    # Finalize framework/tech detection
    detected_fw, detected_db, detected_cloud = set(), set(), set()
    for dep in all_deps:
        for fw, name in get_config_value(lang_config, 'dependencyMaps.Frameworks Detected', {}).items():
            if fw in dep: detected_fw.add(name)
        for db, name in get_config_value(lang_config, 'dependencyMaps.Database Technologies Detected', {}).items():
            if db in dep: detected_db.add(name)
        for cloud, name in get_config_value(lang_config, 'dependencyMaps.Cloud SDKs Detected', {}).items():
            if cloud in dep: detected_cloud.add(name)

    # --- FIX IS HERE ---
    # Dynamically get pattern-based stats, providing a default if the key is missing.
    db_queries_stats = stats['patterns'].get('Database Queries', {'count': 0, 'list': []})
    endpoints_stats = stats['patterns'].get('Endpoints Defined', {'count': 0, 'list': []})
    
    report = {
        "No of Files": stats['composition']['fileCount'],
        "Lines of Code": stats['composition']['totalLinesOfCode'],
        "Functions": stats['composition']['functionCount'],
        "Classes": stats['composition']['classCount'],
        "Avg Complexity": round(stats['complexity']['totalCyclomatic'] / stats['composition']['functionCount'], 2) if stats['composition']['functionCount'] > 0 else 0,
        "Comments": stats['composition']['totalComments'],
        "No of Direct dependencies": len(direct_deps),
        "Direct dependencies All List": list(direct_deps.keys()),
        "Import Frequency": all_deps,
        "DatabaseQueries": db_queries_stats['count'],
        "AllDatabaseQueriesList": list(db_queries_stats['list']),
        "Try/Except Block": stats['quality']['tryCatchCount'],
        "Endpoints defined": endpoints_stats['count'],
        "FrameworksDetected": list(detected_fw),
        "DatabaseDetected": list(detected_db),
        "CloudDetected": list(detected_cloud)
    }
    return report

# --- Main Execution ---
def main(ast_dir: str, config_path: str):
    if not os.path.isdir(ast_dir) or not os.path.isfile(config_path):
        print("Error: AST directory or language configuration not found.", file=sys.stderr)
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        lang_config = json.load(f)

    print(f"Analyzing project using '{lang_config.get('language')}' configuration...")

    stats = {
        'composition': {'fileCount': 0, 'functionCount': 0, 'classCount': 0, 'totalLinesOfCode': 0, 'totalComments': 0},
        'dependencies': {'importCount': 0, 'importFrequency': {}},
        'patterns': {metric: {'count': 0, 'list': set()} for metric in get_config_value(lang_config, 'selectors.patterns', {})},
        'quality': {'tryCatchCount': 0},
        'complexity': {'totalCyclomatic': 0}
    }

    for root, _, files in os.walk(ast_dir):
        for file in files:
            if file.endswith('.json'):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        ast_data = json.load(f)
                    analyze_ast_file(ast_data, stats, lang_config)
                except Exception as e:
                    print(f"\n❌ Failed to analyze file: {full_path}. Reason: {e}", file=sys.stderr)

    final_report = finalize_report(stats, lang_config)
    
    output_file_path = os.path.join(os.getcwd(), 'analysis_report.json')
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(final_report, f, indent=2)
    
    print(f"\n✅ Successfully saved analysis report to: {output_file_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python UniversalParser.py <path-to-ast-directory> <path-to-config.json>")
    else:
        main(sys.argv[1], sys.argv[2])