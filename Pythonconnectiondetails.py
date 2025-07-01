import os
import json
import re

# --- Configuration for Detection ---

# Dictionary mapping database types to their common Python libraries
DB_LIBRARIES = {
    'ORACLE': ['cx_Oracle', 'oracledb'],
    'DB2': ['ibm_db', 'ibm_db_dbi'],
    'MSSQL': ['pyodbc', 'pymssql'],
    'POSTGRES': ['psycopg2', 'pg8000'],
    'SYBASE': ['sybpydb'],
    'MYSQL': ['mysql.connector', 'pymysql', 'flaskext.mysql', 'DBDAO'] # Added DBDAO as a custom keyword
}

def get_imported_modules(node):
    """Traverses the AST to find all imported modules and returns them as a set."""
    imports = set()
    if isinstance(node, dict):
        if node.get("type") in ("import_statement", "import_from_statement"):
            for child in node.get("children", []):
                if child.get("type") == "dotted_name":
                    # Get the base module, e.g., 'routes.user' -> 'routes'
                    base_module = child.get("text", "").split('.')[0]
                    if base_module:
                        imports.add(base_module)
        
        for child in node.get("children", []):
            imports.update(get_imported_modules(child))
            
    elif isinstance(node, list):
        for item in node:
            imports.update(get_imported_modules(item))
            
    return imports

def find_database_connections(node, imported_modules):
    """Recursively finds various database connections based on common libraries and patterns."""
    connections = set()
    if isinstance(node, dict):
        # Look for class instantiations or connect() calls
        if node.get("type") == "call":
            call_text = node.get("text", "")
            # Check if the call is a 'connect' function from an imported DB library
            for db_type, libs in DB_LIBRARIES.items():
                for lib in libs:
                    if lib in imported_modules and f"{lib}.connect" in call_text:
                        connections.add(f"{db_type} connects")
                    # Also check for custom classes like DBDAO
                    if lib in call_text and lib == "DBDAO":
                         connections.add(f"{db_type} connects")


        # Look for specific database configuration, e.g., app.config["MYSQL_DATABASE_HOST"]
        if node.get("type") == "assignment":
            left_side_text = node.get("children", [{}])[0].get("text", "")
            if "MYSQL_DATABASE_HOST" in left_side_text:
                connections.add("MYSQL connects to localhost (inferred from config)")

        # Recurse through children
        for child in node.get("children", []):
            connections.update(find_database_connections(child, imported_modules))

    elif isinstance(node, list):
        for item in node:
            connections.update(find_database_connections(item, imported_modules))
            
    return connections


def find_flask_endpoints(node):
    """Recursively finds Flask endpoints in an AST node."""
    endpoints = set()
    if isinstance(node, dict):
        if node.get("type") == "decorated_definition":
            for deco in (c for c in node.get("children", []) if c.get("type") == "decorator"):
                call_node = next((c for c in deco.get("children", []) if c.get("type") == "call"), None)
                if call_node and ".route" in call_node.get("text", ""):
                    arg_list = next((c for c in call_node.get("children", []) if c.get("type") == "argument_list"), {})
                    
                    path = arg_list.get("children", [{}])[0].get("text", "''").strip("'\"")
                    methods = ["GET"] # Default method

                    methods_arg = next((arg for arg in arg_list.get("children", []) if arg.get("text", "").startswith("methods=")), None)
                    if methods_arg:
                        list_node = next((c for c in methods_arg.get("children", []) if c.get("type") == "list"), {})
                        methods = [m.get("text", "''").strip("'\"") for m in list_node.get("children", [])]
                    
                    for method in methods:
                        endpoints.add(f"{method} {path}")

        for child in node.get("children", []):
            endpoints.update(find_flask_endpoints(child))
            
    elif isinstance(node, list):
        for item in node:
            endpoints.update(find_flask_endpoints(item))
            
    return endpoints

def find_hardcoded_urls(node):
    """Recursively finds hardcoded URLs in string literals."""
    urls = set()
    url_pattern = r'https?://[^\s/$.?#].[^\s]*'

    if isinstance(node, dict):
        if node.get("type") == "string":
            string_content = node.get("text", "").strip("'\"")
            found = re.findall(url_pattern, string_content)
            for url in found:
                urls.add(f"Hardcoded URL: {url}")

        for child in node.get("children", []):
            urls.update(find_hardcoded_urls(child))

    elif isinstance(node, list):
        for item in node:
            urls.update(find_hardcoded_urls(item))
            
    return urls

def parse_ast_file(file_path):
    """Parses a single AST JSON file and extracts relevant information."""
    try:
        with open(file_path, 'r') as f:
            ast_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error reading or parsing {file_path}: {e}")
        return []

    # First, find all imported modules in this file
    imported_modules = get_imported_modules(ast_data)

    # Combine all findings for this file
    findings = set()
    findings.update(find_flask_endpoints(ast_data))
    findings.update(find_database_connections(ast_data, imported_modules))
    findings.update(find_hardcoded_urls(ast_data))

    return sorted(list(findings)) # Return a sorted list for consistent output

def create_connection_graph(root_dir):
    """
    Walks a directory, parses all .py.json files, and builds a connection graph.
    """
    connection_graph = {}
    
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".py.json"):
                full_path = os.path.join(dirpath, filename)
                
                # Create a representative key for the output JSON, like 'routes/user.py'
                relative_path = os.path.relpath(full_path, root_dir)
                original_py_path = relative_path.replace(".json", "").replace("\\", "/")
                
                findings = parse_ast_file(full_path)
                
                if findings:
                    connection_graph[original_py_path] = findings

    return connection_graph

# --- Main Execution ---
if __name__ == "__main__":
    # The script will search for .py.json files in the directory it is run from
    # and all its subdirectories.
    target_directory = "./PythonAST"  # Change this to your target directory if needed
    
    print(f"Starting advanced AST parsing in directory: '{os.path.abspath(target_directory)}'...")
    
    # Generate the graph
    graph = create_connection_graph(target_directory)
    
    # Convert the graph to a pretty-printed JSON string
    output_json = json.dumps(graph, indent=2)
    
    print("\n--- Generated Connection Graph ---")
    print(output_json)
    
    output_filename = "connection_graph_detailed.json"
    try:
        with open(output_filename, "w") as f_out:
            f_out.write(output_json)
        print(f"\nSuccessfully saved to {output_filename}")
    except IOError as e:
        print(f"\nCould not save output file: {e}")