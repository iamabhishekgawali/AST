import os
import json
import re
from collections import defaultdict

def find_specific_api_calls(node, file_path, results):
    """
    Recursively traverses the AST to find specific API calls like fetch, axios, etc.
    """
    if not isinstance(node, dict):
        return

    node_type = node.get("type")

    # Pattern for fetch('api/endpoint', ...) or axios.get('api/endpoint', ...)
    if node_type == "call_expression":
        # The 'callee' is the function being called.
        callee = node.get("children", [{}])[0]
        callee_type = callee.get("type")
        callee_text = callee.get("text", "")

        method = ""
        endpoint = "unknown_endpoint"
        call_type = ""

        # Check for fetch()
        if callee_type == "identifier" and callee_text == "fetch":
            call_type = "FETCH"
            method = "GET" # Default method for fetch if not specified
        
        # Check for axios.get(), axios.post(), etc.
        elif callee_type == "member_expression":
            axios_match = re.match(r'axios\.(get|post|put|delete)', callee_text)
            if axios_match:
                call_type = "AXIOS"
                method = axios_match.group(1).upper()

        if call_type:
            # The arguments to the call
            args_node = node.get("children", [{}, {}])[1]
            if args_node and args_node.get("children"):
                endpoint_node = args_node.get("children")[0]
                endpoint = endpoint_node.get("text", "'unknown'").strip("'\"")
            
            results['api_calls'].append(f"{file_path} \t {call_type} ({method}) \t {endpoint}")

    # Pattern for new XMLHttpRequest()
    elif node_type == "new_expression":
        callee = node.get("children", [{}])[0]
        if callee.get("type") == "identifier" and callee.get("text") == "XMLHttpRequest":
            results['api_calls'].append(f"{file_path} \t XMLHTTPREQUEST")

    # Recurse through children nodes
    if "children" in node and isinstance(node["children"], list):
        for child in node["children"]:
            find_specific_api_calls(child, file_path, results)


def parse_ast_files_for_api_calls(root_folder):
    """
    Parses all JSON AST files in a folder to find specific API calls.
    """
    if not os.path.isdir(root_folder):
        print(f"Error: Directory '{root_folder}' not found.")
        return None
    
    all_results = defaultdict(list)

    for dirpath, _, filenames in os.walk(root_folder):
        for filename in filenames:
            if filename.endswith(".json"):
                file_path = os.path.join(dirpath, filename)
                relative_path = os.path.relpath(file_path, root_folder)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        ast_data = json.load(f)
                    
                    find_specific_api_calls(ast_data, relative_path, all_results)

                except Exception as e:
                    print(f"An error occurred while processing {relative_path}: {e}")

    # Remove duplicates
    for key, values in all_results.items():
        all_results[key] = sorted(list(set(values)))

    return dict(all_results)

def main():
    """
    Main function to execute the parsing script.
    """
    folder_name = "ast_files" # Using the same folder as before

    # Run the specific API call parser
    parsed_data = parse_ast_files_for_api_calls(folder_name)
    
    # Print the results
    if parsed_data:
        print(json.dumps(parsed_data, indent=2))
    else:
        print(json.dumps({"api_calls": ["No specific API calls (fetch, axios, XMLHttpRequest) were found in the provided AST files."]}, indent=2))

if __name__ == '__main__':
    main()