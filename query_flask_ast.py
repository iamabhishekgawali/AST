import os
import json
import re

def find_nodes_by_type(node, node_type):
    """
    Recursively finds all nodes of a specific type in the native Python AST JSON.
    """
    nodes = []
    if isinstance(node, dict):
        if node.get('node_type') == node_type:
            nodes.append(node)
        for key, value in node.items():
            nodes.extend(find_nodes_by_type(value, node_type))
    elif isinstance(node, list):
        for item in node:
            nodes.extend(find_nodes_by_type(item, node_type))
    return nodes

def analyze_file(ast_data):
    """
    Analyzes a single serialized AST file and returns its metrics.
    This version is tailored to the output of Python's native 'ast' module.
    """
    metrics = {}
    
    # --- 1. Code Composition & Complexity ---
    functions = find_nodes_by_type(ast_data, 'FunctionDef')
    classes = find_nodes_by_type(ast_data, 'ClassDef')
    
    # Correctly calculate lines of code from the module's body
    last_node = ast_data.get('body', [])[-1] if ast_data.get('body') else {}
    metrics['linesOfCode'] = last_node.get('end_lineno', 1)
    metrics['functionCount'] = len(functions)
    metrics['classCount'] = len(classes)
    metrics['commentCount'] = 0 # Native AST does not parse comments by default.

    # --- 2. Dependency Analysis ---
    imports = []
    import_froms = find_nodes_by_type(ast_data, 'ImportFrom')
    for imp in import_froms:
        if imp.get('module'):
            imports.append(imp['module'])
            
    import_nodes = find_nodes_by_type(ast_data, 'Import')
    for imp in import_nodes:
        for alias in imp.get('names', []):
            imports.append(alias['name'])

    metrics['imports'] = imports

    # --- 3. API & Service Usage ---
    decorators = find_nodes_by_type(ast_data, 'Call')
    flask_endpoints = [
        d for d in decorators 
        if d.get('func', {}).get('value', {}).get('id') == 'router' and d.get('func', {}).get('attr') == 'route'
    ]
    metrics['apiEndpointDefinitions'] = len(flask_endpoints)
    
    # --- 4. Quality & Maintainability ---
    metrics['exceptionHandlers'] = len(find_nodes_by_type(ast_data, 'ExceptHandler'))

    # --- 6. Security ---
    calls = find_nodes_by_type(ast_data, 'Call')
    metrics['userInputHandlers'] = len([c for c in calls if c.get('func', {}).get('attr') == 'get_json'])
    metrics['permissionChecks'] = len([d for d in find_nodes_by_type(ast_data, 'Name') if d.get('id') == 'secure_route'])


    # These metrics are harder to get accurately with native AST vs tree-sitter, but we provide estimates
    metrics['networkCalls'] = len([c for c in calls if c.get('func', {}).get('value', {}).get('id') == 'requests'])
    metrics['fileIoOperations'] = len([c for c in calls if c.get('func', {}).get('id') == 'open'])
    metrics['totalCyclomaticComplexity'] = sum(len(find_nodes_by_type(f, 'If')) + 1 for f in functions)
    metrics['maxNestingDepth'] = 0 # Complex to calculate with this AST format

    return metrics

def aggregate_report(all_file_metrics):
    """Aggregates metrics from all files into a single, comprehensive report."""
    report = {
        'codeComposition': {'numberOfFiles': 0, 'numberOfClasses': 0, 'numberOfFunctions': 0, 'linesOfCodePerFile': {}, 'totalLinesOfCode': 0, 'maxNestingDepth': 0, 'totalCyclomaticComplexity': 0, 'totalCommentCount': 0, 'averageCyclomaticComplexity': 0, 'commentToCodeRatio': 0},
        'dependencyAnalysis': {'importsByType': {'internal': 0, 'external': 0}, 'importFrequency': {}, 'directDependencies': [], 'thirdPartyVsInHouseRatio': 0},
        'apiAndServiceUsage': {'totalNetworkCalls': 0, 'totalApiEndpointsDefined': 0, 'totalFileIoOperations': 0, 'listOfHardcodedUrlsAndIPs': []},
        'qualityAndMaintainability': {'totalTodosAndFixmes': 0, 'totalDeprecatedApiCalls': 0, 'totalExceptionHandlers': 0},
        'applicationStructure': {'numberOfModules': 0, 'distributionOfCodeByLayer': {}, 'sizeOfEachModuleByLines': {}},
        'security': {'totalUserInputHandlers': 0, 'totalCryptoUsage': 0, 'totalPermissionChecks': 0}
    }

    for file_path, metrics in all_file_metrics.items():
        # Composition
        report['codeComposition']['numberOfFiles'] += 1
        report['codeComposition']['numberOfClasses'] += metrics.get('classCount', 0)
        report['codeComposition']['numberOfFunctions'] += metrics.get('functionCount', 0)
        report['codeComposition']['linesOfCodePerFile'][file_path] = metrics.get('linesOfCode', 0)
        report['codeComposition']['totalLinesOfCode'] += metrics.get('linesOfCode', 0)
        report['codeComposition']['maxNestingDepth'] = max(report['codeComposition']['maxNestingDepth'], metrics.get('maxNestingDepth', 0))
        report['codeComposition']['totalCyclomaticComplexity'] += metrics.get('totalCyclomaticComplexity', 0)
        report['codeComposition']['totalCommentCount'] += metrics.get('commentCount', 0)

        # Dependencies
        for imp in metrics.get('imports', []):
            if not imp: continue
            # A simple heuristic for internal vs external
            if '.' in imp or file_path.split(os.sep)[0] in imp:
                report['dependencyAnalysis']['importsByType']['internal'] += 1
            else:
                report['dependencyAnalysis']['importsByType']['external'] += 1
            report['dependencyAnalysis']['importFrequency'][imp] = report['dependencyAnalysis']['importFrequency'].get(imp, 0) + 1

        # API, Quality, Security, Structure
        report['apiAndServiceUsage']['totalNetworkCalls'] += metrics.get('networkCalls', 0)
        report['apiAndServiceUsage']['totalApiEndpointsDefined'] += metrics.get('apiEndpointDefinitions', 0)
        report['apiAndServiceUsage']['totalFileIoOperations'] += metrics.get('fileIoOperations', 0)
        report['qualityAndMaintainability']['totalExceptionHandlers'] += metrics.get('exceptionHandlers', 0)
        report['security']['totalUserInputHandlers'] += metrics.get('userInputHandlers', 0)
        report['security']['totalPermissionChecks'] += metrics.get('permissionChecks', 0)
        
        module_dir = os.path.dirname(file_path)
        if module_dir:
            report['applicationStructure']['sizeOfEachModuleByLines'][module_dir] = report['applicationStructure']['sizeOfEachModuleByLines'].get(module_dir, 0) + metrics.get('linesOfCode', 0)
            layer = module_dir.split(os.sep)[0]
            report['applicationStructure']['distributionOfCodeByLayer'][layer] = report['applicationStructure']['distributionOfCodeByLayer'].get(layer, 0) + 1

    # Final Calculations
    comp = report['codeComposition']
    if comp.get('numberOfFunctions', 0) > 0: comp['averageCyclomaticComplexity'] = comp.get('totalCyclomaticComplexity', 0) / comp['numberOfFunctions']
    if comp.get('totalLinesOfCode', 0) > 0: comp['commentToCodeRatio'] = comp.get('totalCommentCount', 0) / comp['totalLinesOfCode']
    
    deps = report['dependencyAnalysis']
    deps['directDependencies'] = list(deps['importFrequency'].keys())
    if deps['importsByType'].get('internal', 0) > 0:
        deps['thirdPartyVsInHouseRatio'] = deps['importsByType'].get('external', 0) / deps['importsByType']['internal']
    else:
        deps['thirdPartyVsInHouseRatio'] = float('inf') if deps['importsByType'].get('external', 0) > 0 else 0

    report['applicationStructure']['numberOfModules'] = len(report['applicationStructure']['sizeOfEachModuleByLines'])

    return report


def process_directory(ast_dir):
    """Processes all AST files in a directory."""
    all_metrics = {}
    for root, _, files in os.walk(ast_dir):
        for file in files:
            if file.endswith('.json'):
                full_path = os.path.join(root, file)
                original_path = os.path.relpath(full_path, ast_dir)[:-5]
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        ast_data = json.load(f)
                    all_metrics[original_path] = analyze_file(ast_data)
                except Exception as e:
                    print(f"[ERROR] Failed to process {full_path}: {e}")
    return all_metrics

if __name__ == "__main__":
    ast_directory = "./ast_output_python"
    report_output_file = "./analysis_report_python.json"

    if not os.path.exists(ast_directory):
        print(f"[ERROR] AST output directory not found at '{ast_directory}'. Please run 'parse_flask_project.py' first.")
    else:
        print(f"Analyzing AST files from '{ast_directory}'...")
        all_file_metrics = process_directory(ast_directory)
        
        print("Aggregating data into a single project report...")
        final_report = aggregate_report(all_file_metrics)

        with open(report_output_file, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, indent=2)
            
        print(f"\n✅ Analysis complete! A single, comprehensive report has been saved to '{report_output_file}'")
