import os
import json

def find_flask_endpoints(node, file_path):
    """Recursively finds Flask endpoints in an AST node."""
    endpoints = []
    if isinstance(node, dict):
        # Check if it's a decorated function definition, typical for routes
        if node.get("type") == "decorated_definition":
            decorators = [child for child in node.get("children", []) if child.get("type") == "decorator"]
            for deco in decorators:
                # The decorator itself is a call, e.g., @app.route(...)
                call_node = next((child for child in deco.get("children", []) if child.get("type") == "call"), None)
                if not call_node:
                    continue

                # Check if the function being called is 'route'
                attribute_node = next((child for child in call_node.get("children", []) if child.get("type") == "attribute"), None)
                if attribute_node and attribute_node.get("text", "").endswith(".route"):
                    arg_list = next((child for child in call_node.get("children", []) if child.get("type") == "argument_list"), None)
                    if not arg_list:
                        continue
                    
                    # Extract path (first argument)
                    path_node = arg_list.get("children", [])[0]
                    path = path_node.get("text", "''").strip("'\"")

                    # Extract methods (keyword argument), default to GET
                    methods = ["GET"]
                    methods_kw_arg = next((arg for arg in arg_list.get("children", []) if arg.get("type") == "keyword_argument" and arg.get("text", "").startswith("methods=")), None)
                    if methods_kw_arg:
                        list_node = next((child for child in methods_kw_arg.get("children", []) if child.get("type") == "list"), None)
                        if list_node:
                            methods = [m.get("text", "''").strip("'\"") for m in list_node.get("children", [])]
                    
                    for method in methods:
                        endpoints.append(f"{method} {path}")

        # Recursively search in children
        for child in node.get("children", []):
            endpoints.extend(find_flask_endpoints(child, file_path))
            
    elif isinstance(node, list):
        for item in node:
            endpoints.extend(find_flask_endpoints(item, file_path))
            
    return endpoints

def find_db_connections(node, file_path):
    """Recursively finds database connections in an AST node."""
    connections = []
    if isinstance(node, dict):
        # Look for class instantiations like MySQL() or DBDAO()
        if node.get("type") == "call":
            identifier = next((child.get("text") for child in node.get("children", []) if child.get("type") == "identifier"), None)
            if identifier in ["MySQL", "DBDAO"]:
                 connections.append("MYSQL connects")

        # Look for database configuration, e.g., app.config["MYSQL_DATABASE_HOST"]
        if node.get("type") == "assignment":
             left_side = node.get("children", [])[0]
             if left_side.get("type") == "subscript" and "MYSQL_DATABASE_HOST" in left_side.get("text", ""):
                 right_side = node.get("children", [])[1]
                 # Extract hostname if available
                 hostname = "unknown"
                 if right_side.get("type") == "attribute" and right_side.get("text") == "self.host":
                    # In a real scenario, you'd trace self.host back, here we simplify
                    hostname = "localhost (inferred)" 
                 elif right_side.get("type") == "string":
                     hostname = right_side.get("text", '""').strip("'\"")
                 connections.append(f"MYSQL connects to {hostname}")

        # Recurse through children
        for child in node.get("children", []):
            connections.extend(find_db_connections(child, file_path))

    elif isinstance(node, list):
        for item in node:
            connections.extend(find_db_connections(item, file_path))
            
    return connections

def parse_ast_file(file_path):
    """Parses a single AST JSON file and extracts relevant information."""
    try:
        with open(file_path, 'r') as f:
            ast_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error reading or parsing {file_path}: {e}")
        return []

    # Combine all findings for this file
    findings = []
    findings.extend(find_flask_endpoints(ast_data, file_path))
    findings.extend(find_db_connections(ast_data, file_path))
    # Note: Socket and external API call detection would be added here
    # but are omitted as they are not present in the example files.

    return list(set(findings)) # Use set to remove duplicates

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
                original_py_path = relative_path.replace(".json", "").replace("\\", "/") # Normalize path separators
                
                # Parse the file and get findings
                findings = parse_ast_file(full_path)
                
                if findings:
                    if original_py_path not in connection_graph:
                        connection_graph[original_py_path] = []
                    connection_graph[original_py_path].extend(findings)

    return connection_graph

# --- Main Execution ---
if __name__ == "__main__":
    # IMPORTANT: Replace '.' with the actual path to the folder 
    # containing your AST files (e.g., 'path/to/your/ast_folder').
    # For this example, it assumes the script is run in a directory 
    # that has the 'routes', 'Models', etc. subdirectories.
    target_directory = "." 
    
    print(f"Starting AST parsing in directory: '{os.path.abspath(target_directory)}'...")
    
    # Generate the graph
    graph = create_connection_graph(target_directory)
    
    # Convert the graph to a pretty-printed JSON string
    output_json = json.dumps(graph, indent=2)
    
    # Print the final JSON to the console
    print("\n--- Generated Connection Graph ---")
    print(output_json)
    
    # Optionally, save to a file
    try:
        with open("connection_graph.json", "w") as f_out:
            f_out.write(output_json)
        print("\nSuccessfully saved to connection_graph.json")
    except IOError as e:
        print(f"\nCould not save output file: {e}")