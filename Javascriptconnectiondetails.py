import os
import json
import re
from collections import defaultdict

def find_api_or_route_in_node(node, file_path, results):
    """
    Recursively traverses the AST to find API calls or route definitions.
    """
    if not isinstance(node, dict):
        return

    # Pattern for Express-style routes (e.g., app.get('/api', ...))
    if node.get("type") == "call_expression":
        member_expr = node.get("children", [{}])[0]
        if member_expr.get("type") == "member_expression":
            text = member_expr.get("text", "")
            match = re.match(r'app\.(get|post|put|delete|use)|router\.(get|post|put|delete|use)', text)
            if match:
                method = text.split('.')[-1].upper()
                args = node.get("children", [{}, {}])[1].get("children", [])
                if args:
                    path_node = args[0]
                    path = path_node.get("text", "unknown_path").strip("'\"")
                    results['api_calls'].append(f"{file_path} \t {method} \t {path}")

    # Fallback for broken JSX ASTs by parsing the text content
    node_text = node.get("text", "")
    # Pattern for JSX-style routes (e.g., <Route path="/home" ... />)
    route_matches = re.findall(r'<(?:Route|PublicRoute|AdminRoute|ClientRoute)\s+[^>]*?path=(?:\{([^}]+)\}|"([^"]+)")', node_text, re.DOTALL)

    for match in route_matches:
        # match will be a tuple, e.g., ('ROUTES.HOME', '') or ('', '/home')
        path_value = match[0] if match[0] else match[1]
        path_value = path_value.replace('`', '').replace('${', '{').strip()
        # Cannot determine HTTP method from React Router, so we label it as 'ROUTE'
        results['api_calls'].append(f"{file_path} \t ROUTE \t {path_value}")


    # Recursively check children
    if "children" in node and isinstance(node["children"], list):
        for child in node["children"]:
            find_api_or_route_in_node(child, file_path, results)


def find_socket_info_in_node(node, file_path, results):
    """
    Recursively traverses the AST to find socket connection details.
    """
    if not isinstance(node, dict):
        return

    # Pattern for server.listen(PORT, ...)
    if node.get("type") == "call_expression":
        member_expr = node.get("children", [{}])[0]
        if member_expr.get("type") == "member_expression" and member_expr.get("text") == "server.listen":
            args_node = node.get("children", [{}, {}])[1]
            first_arg = args_node.get("children", [{}])[0]
            port = "unknown"
            if first_arg.get("type") == "binary_expression":  # Handles `process.env.PORT || 5000`
                for child in first_arg.get("children", []):
                    if child.get("type") == "number":
                        port = child.get("text")
                        break
            elif first_arg.get("type") == "number":
                port = first_arg.get("text")
            results['socket_connections'].append(f"{file_path} \t Socket connects \t port {port}")

        # Pattern for socket.on('event', ...)
        elif member_expr.get("type") == "member_expression" and member_expr.get("text") == "socket.on":
            args_node = node.get("children", [{}, {}])[1]
            first_arg = args_node.get("children", [{}])[0]
            if first_arg.get("type") == "string":
                event_name = first_arg.get("text", "'unknown_event'").strip("'")
                results['socket_connections'].append(f"{file_path} \t Socket event \t {event_name}")


    # Recursively check children
    if "children" in node and isinstance(node["children"], list):
        for child in node["children"]:
            find_socket_info_in_node(child, file_path, results)

def parse_ast_files(root_folder):
    """
    Parses all JSON AST files in a given folder and its subdirectories.

    Args:
        root_folder (str): The path to the root folder to search.

    Returns:
        dict: A dictionary containing lists of found API calls and socket connections.
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

                    # Create a temporary dict for the current file's results
                    file_results = defaultdict(list)

                    find_api_or_route_in_node(ast_data, relative_path, file_results)
                    find_socket_info_in_node(ast_data, relative_path, file_results)

                    # Remove duplicates and add to the main results
                    for key, values in file_results.items():
                        unique_values = sorted(list(set(values)))
                        all_results[key].extend(unique_values)

                except json.JSONDecodeError:
                    print(f"Warning: Could not decode JSON from {relative_path}")
                except Exception as e:
                    print(f"An error occurred while processing {relative_path}: {e}")

    return dict(all_results)

def main():
    """
    Main function to execute the parsing script.
    """
    # Create a dummy folder structure for demonstration
    # In a real scenario, this would be the path to your AST files.
    folder_name = "./JavaScriptAST"
    if not os.path.exists(folder_name):
        os.makedirs(os.path.join(folder_name, "routes"))
        os.makedirs(os.path.join(folder_name, "utils"))
        os.makedirs(os.path.join(folder_name, "server"))


    # Dummy file contents based on user-provided data
    files_content = {
        os.path.join("server", "index.js.json"): """{ "type": "program", "text": "const http = require('http');\\r\\nconst express = require('express');\\r\\nconst socketio = require('socket.io');\\r\\nconst cors = require('cors');\\r\\n\\r\\nconst { addUser, removeUser, getUser, getUsersInRoom } = require('./users');\\r\\n\\r\\nconst router = require('./router');\\r\\n\\r\\nconst app = express();\\r\\nconst server = http.createServer(app);\\r\\nconst io = socketio(server);\\r\\n\\r\\napp.use(cors());\\r\\napp.use(router);\\r\\n\\r\\nio.on('connect', (socket) => {\\r\\n  socket.on('join', ({ name, room }, callback) => {\\r\\n    const { error, user } = addUser({ id: socket.id, name, room });\\r\\n\\r\\n    if(error) return callback(error);\\r\\n\\r\\n    socket.join(user.room);\\r\\n\\r\\n    socket.emit('message', { user: 'admin', text: `${user.name}, welcome to room ${user.room}.`});\\r\\n    socket.broadcast.to(user.room).emit('message', { user: 'admin', text: `${user.name} has joined!` });\\r\\n\\r\\n    io.to(user.room).emit('roomData', { room: user.room, users: getUsersInRoom(user.room) });\\r\\n\\r\\n    callback();\\r\\n  });\\r\\n\\r\\n  socket.on('sendMessage', (message, callback) => {\\r\\n    const user = getUser(socket.id);\\r\\n\\r\\n    io.to(user.room).emit('message', { user: user.name, text: message });\\r\\n\\r\\n    callback();\\r\\n  });\\r\\n\\r\\n  socket.on('disconnect', () => {\\r\\n    const user = removeUser(socket.id);\\r\\n\\r\\n    if(user) {\\r\\n      io.to(user.room).emit('message', { user: 'Admin', text: `${user.name} has left.` });\\r\\n      io.to(user.room).emit('roomData', { room: user.room, users: getUsersInRoom(user.room)});\\r\\n    }\\r\\n  })\\r\\n});\\r\\n\\r\\nserver.listen(process.env.PORT || 5000, () => console.log(`Server has started.`));", "children": [ { "type": "expression_statement", "children": [ { "type": "call_expression", "children": [ { "type": "member_expression", "text": "server.listen" }, { "type": "arguments", "children": [ { "type": "binary_expression", "children": [ { "type": "member_expression", "text": "process.env.PORT" }, { "type": "number", "text": "5000" } ] } ] } ] } ] }, { "type": "expression_statement", "children": [ { "type": "call_expression", "children": [ { "type": "member_expression", "text": "io.on" }, { "type": "arguments", "children": [ { "type": "string", "text": "'connect'" }, { "type": "arrow_function", "children": [ {}, { "type": "statement_block", "children": [ { "type": "expression_statement", "children": [ { "type": "call_expression", "children": [ { "type": "member_expression", "text": "socket.on" }, { "type": "arguments", "children": [ { "type": "string", "text": "'join'" } ] } ] } ] }, { "type": "expression_statement", "children": [ { "type": "call_expression", "children": [ { "type": "member_expression", "text": "socket.on" }, { "type": "arguments", "children": [ { "type": "string", "text": "'sendMessage'" } ] } ] } ] }, { "type": "expression_statement", "children": [ { "type": "call_expression", "children": [ { "type": "member_expression", "text": "socket.on" }, { "type": "arguments", "children": [ { "type": "string", "text": "'disconnect'" } ] } ] } ] } ] } ] } ] } ] } ] } ] }""",
        os.path.join("routes", "AppRouter.jsx.json"): """{ "type": "ERROR", "text": "import * as ROUTES from '@/constants/routes';\\n <Router>\\n <Switch>\\n <Route component={view.Search} exact path={ROUTES.SEARCH} />\\n <Route component={view.Home} exact path={ROUTES.HOME} />\\n <AdminRoute component={view.EditProduct} path={`${ROUTES.EDIT_PRODUCT}/:id`} />\\n </Switch>\\n </Router>" }""",
        os.path.join("routes", "PublicRoute.jsx.json"): """{ "type": "program", "text": "() => <Redirect to={SIGNIN} />" }""",
        os.path.join("utils", "users.js.json"): """{ "type": "program", "text": "const users = []; module.exports = { users };" }"""
    }

    # Write dummy files
    for path, content in files_content.items():
        full_path = os.path.join(folder_name, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

    # Run the parser and get the results
    parsed_data = parse_ast_files(folder_name)

    # Print the results as a JSON object
    if parsed_data:
        print(json.dumps(parsed_data, indent=2))

if __name__ == '__main__':
    main()