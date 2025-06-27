# To run this script:
# 1. First, generate the ASTs using the python_ast_generator.py script.
# 2. Make sure the ASTs are in a directory named 'PythonAST'.
# 3. Execute this script from your terminal, passing the path to the AST directory:
#    python analyze_python_ast.py ./PythonAST

import json
import os
import sys

# --- Helper Functions for Analysis ---

def find_nodes_by_type(node, type_name):
    """
    Recursively finds all nodes of a specific type in the AST.
    """
    nodes = []
    if not isinstance(node, dict) or not node:
        return nodes

    if node.get('type') == type_name:
        nodes.append(node)

    for child in node.get('children', []):
        nodes.extend(find_nodes_by_type(child, type_name))
        
    return nodes

def calculate_cyclomatic_complexity(function_node):
    """
    Calculates the cyclomatic complexity for a Python function node.
    """
    complexity = 1
    # Python-specific branching nodes
    branching_types = [
        'if_statement', 'for_statement', 'while_statement', 
        'except_clause', 'assert_statement', 'with_statement'
    ]
    # 'and' and 'or' in boolean operators also add to complexity
    logical_operators = find_nodes_by_type(function_node, 'boolean_operator')
    complexity += len(logical_operators)
    
    for branch_type in branching_types:
        complexity += len(find_nodes_by_type(function_node, branch_type))
        
    return complexity

def analyze_ast_file(file_path, stats):
    """
    Analyzes a single AST file and aggregates statistics based on observed structures.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            ast_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[ERROR] Could not read or parse {file_path}: {e}")
        return

    if not ast_data:
        return

    # --- 1. Code Composition & Complexity ---
    stats['composition']['fileCount'] += 1
    lines = ast_data.get('endPosition', {}).get('row', 0) - ast_data.get('startPosition', {}).get('row', 0) + 1
    stats['composition']['totalLinesOfCode'] += lines
    
    functions = find_nodes_by_type(ast_data, 'function_definition')
    stats['composition']['functionCount'] += len(functions)
    stats['composition']['classCount'] += len(find_nodes_by_type(ast_data, 'class_definition'))
    
    comments = find_nodes_by_type(ast_data, 'comment')
    stats['composition']['totalComments'] += len(comments)

    for func in functions:
        stats['complexity']['totalCyclomatic'] += calculate_cyclomatic_complexity(func)

    # --- 2. Dependency Analysis ---
    imports = find_nodes_by_type(ast_data, 'import_statement')
    imports_from = find_nodes_by_type(ast_data, 'import_from_statement')
    stats['dependencies']['importCount'] += len(imports) + len(imports_from)

    all_imports = imports + imports_from
    for imp in all_imports:
        source_node = next((c for c in imp.get('children', []) if c.get('type') in ['dotted_name', 'relative_import']), None)
        if source_node:
            source = source_node.get('text', '')
            stats['dependencies']['importFrequency'][source] = stats['dependencies']['importFrequency'].get(source, 0) + 1
            if source.startswith('.'):
                 stats['dependencies']['internalImports'] += 1
            else:
                 stats['dependencies']['externalImports'] += 1
                 if 'boto3' in source or 'google.cloud' in source:
                     stats['infra']['cloudSDKs'].add('AWS' if 'boto3' in source else 'Google Cloud')
                 if 'pymongo' in source:
                      stats['infra']['databaseTech'].add('MongoDB')
                 if 'flask' in source:
                      stats['frameworks']['detected'].add('Flask')
                 if 'django' in source:
                      stats['frameworks']['detected'].add('Django')


    # --- 3. API, Service, and Infrastructure Usage ---
    call_expressions = find_nodes_by_type(ast_data, 'call')
    for call in call_expressions:
        call_text = call.get('text', '')
        if any(keyword in call_text for keyword in ['requests.', 'httpx.', 'urllib.request']):
            stats['api']['networkCallCount'] += 1
        # Structural check for DB queries (more robust)
        if call.get('children'):
            function_call_node = call['children'][0]
            if function_call_node.get('type') == 'attribute' and any(db_call in function_call_node.get('text', '') for db_call in ['.query', '.execute', '.fetchone', '.fetchall', '.insert_one', '.find_one', '.add', '.commit']):
                 stats['api']['databaseQueries'] += 1
        
        if 'open(' in call_text:
            stats['api']['fileIOCount'] += 1
        if 'os.getenv' in call_text or 'os.environ' in call_text:
            arg_list = find_nodes_by_type(call, 'argument_list')
            if arg_list and arg_list[0].get('children'):
                 env_var_node = find_nodes_by_type(arg_list[0], 'string')
                 if env_var_node:
                    stats['infra']['environmentVariables'].add(env_var_node[0].get('text', ''))
    
    # --- 4. Code Quality & Maintainability ---
    stats['quality']['tryExceptCount'] += len(find_nodes_by_type(ast_data, 'try_statement'))
    for comment in comments:
        if 'TODO' in comment.get('text', '').upper() or 'FIXME' in comment.get('text', '').upper():
            stats['quality']['todoFixmeCount'] += 1
    if file_path.startswith('test') or file_path.endswith('_test.py') or 'test' in file_path:
        stats['quality']['testFileCount'] += 1
        
    # --- 5. Python-Specific & Framework Patterns ---
    stats['pythonSpecifics']['fStrings'] += len([s for s in find_nodes_by_type(ast_data, 'string') if s.get('text', '').startswith('f')])
    stats['pythonSpecifics']['listComprehensions'] += len(find_nodes_by_type(ast_data, 'list_comprehension'))
    
    # Structural check for Flask/Django routes
    decorated_defs = find_nodes_by_type(ast_data, 'decorated_definition')
    for dec_def in decorated_defs:
        for decorator_node in dec_def.get('children', []):
            if decorator_node.get('type') == 'decorator':
                dec_text = decorator_node.get('text', '')
                if '@app.route' in dec_text or '.route(' in dec_text:
                    stats['frameworks']['endpointsDefined'] += 1
                    # Extract endpoint path
                    route_call = find_nodes_by_type(decorator_node, 'call')
                    if route_call:
                        arg_list = find_nodes_by_type(route_call[0], 'argument_list')
                        if arg_list:
                            string_node = find_nodes_by_type(arg_list[0], 'string')
                            if string_node:
                                stats['api']['endpointPaths'].add(string_node[0].get('text'))
    
    # Heuristic for Django Models
    for class_node in find_nodes_by_type(ast_data, 'class_definition'):
        arg_list = find_nodes_by_type(class_node, 'argument_list')
        if arg_list and 'models.Model' in arg_list[0].get('text', ''):
             stats['frameworks']['djangoModels'] += 1


# --- Main Execution ---
def main(ast_dir):
    if not os.path.isdir(ast_dir):
        print(f"Error: Directory not found at '{ast_dir}'")
        sys.exit(1)

    # Initialize stats structure
    stats = {
        'composition': {'fileCount': 0, 'functionCount': 0, 'classCount': 0, 'totalLinesOfCode': 0, 'totalComments': 0},
        'complexity': {'totalCyclomatic': 0},
        'dependencies': {'importCount': 0, 'internalImports': 0, 'externalImports': 0, 'importFrequency': {}},
        'api': {'endpointsDefined': 0, 'endpointPaths': set(), 'networkCallCount': 0, 'databaseQueries': 0, 'fileIOCount': 0},
        'quality': {'todoFixmeCount': 0, 'tryExceptCount': 0, 'testFileCount': 0},
        'pythonSpecifics': {'fStrings': 0, 'listComprehensions': 0},
        'frameworks': {'detected': set(), 'endpointsDefined': 0, 'djangoModels': 0},
        'infra': {'environmentVariables': set(), 'databaseTech': set(), 'cloudSDKs': set()}
    }

    for root, _, files in os.walk(ast_dir):
        for file in files:
            if file.endswith('.json'):
                analyze_ast_file(os.path.join(root, file), stats)
    
    # --- Final Calculations & Formatting ---
    if stats['composition']['functionCount'] > 0:
        stats['complexity']['averageCyclomatic'] = round(stats['complexity']['totalCyclomatic'] / stats['composition']['functionCount'], 2)
    else:
        stats['complexity']['averageCyclomatic'] = 0
        
    stats['infra']['environmentVariables'] = list(stats['infra']['environmentVariables'])
    stats['infra']['cloudSDKs'] = list(stats['infra']['cloudSDKs'])
    stats['infra']['databaseTech'] = list(stats['infra']['databaseTech'])
    stats['frameworks']['detected'] = list(stats['frameworks']['detected'])
    stats['api']['endpointPaths'] = list(stats['api']['endpointPaths'])
    
    external_deps = {k: v for k, v in stats['dependencies']['importFrequency'].items() if not k.startswith('.')}
    
    # Structure the final report
    final_report = {
        "Code Composition & Complexity": {
            "Number of files": stats['composition']['fileCount'],
            "Total lines of code": stats['composition']['totalLinesOfCode'],
            "Number of functions": stats['composition']['functionCount'],
            "Number of classes": stats['composition']['classCount'],
            "Average cyclomatic complexity": stats['complexity']['averageCyclomatic'],
            "Total number of comments": stats['composition']['totalComments'],
        },
        "Dependency Analysis": {
            "Number of import statements": stats['dependencies']['importCount'],
            "Types of imports (internal vs. external)": f"{stats['dependencies']['internalImports']} vs. {stats['dependencies']['externalImports']}",
            "List of direct dependencies": list(external_deps.keys()),
            "Import frequency by module/library": stats['dependencies']['importFrequency'],
        },
        "API and Service Usage": {
            "Endpoints Defined": stats['frameworks']['endpointsDefined'],
            "Endpoint Paths": stats['api']['endpointPaths'],
            "Database Queries (heuristic)": stats['api']['databaseQueries'],
            "Outbound Network Calls (heuristic)": stats['api']['networkCallCount'],
            "File I/O Operations": stats['api']['fileIOCount'],
        },
        "Code Quality & Maintainability": {
            "Number of TODO / FIXME comments": stats['quality']['todoFixmeCount'],
            "Number of try/except blocks": stats['quality']['tryExceptCount'],
            "Number of test files": stats['quality']['testFileCount'],
        },
        "Python-Specific Patterns": stats['pythonSpecifics'],
        "Framework & Infrastructure": {
            "Frameworks Detected": stats['frameworks']['detected'],
            "Django Models Defined": stats['frameworks']['djangoModels'],
            "Environment Variables Accessed": stats['infra']['environmentVariables'],
            "Database Technologies Detected": stats['infra']['databaseTech'],
            "Cloud SDKs Detected": stats['infra']['cloudSDKs'],
        }
    }

    # Save report
    output_path = os.path.join(os.getcwd(), 'python_analysis_report.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_report, f, indent=2)
        
    print(f"\n✅ Successfully saved Python analysis report to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_python_ast.py <path-to-PythonAST-directory>")
        sys.exit(1)
    
    ast_directory = sys.argv[1]
    main(ast_directory)
