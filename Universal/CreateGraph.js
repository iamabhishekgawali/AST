const fs = require("fs");
const path = require("path");

// --- Configuration ---
const astDir = path.join(__dirname, "./JavascriptAST"); // Directory containing the AST .json files
const dotFilePath = path.join(__dirname, "dependencies.dot"); // Output .dot file path

// --- Graph Data Structures ---
// Using Sets to automatically handle duplicate nodes and edges
const nodes = new Set();
const edges = new Set();

/**
 * Adds a node to the graph.
 * @param {string} id - A unique identifier for the node.
 * @param {string} label - The text to display for the node.
 * @param {string} type - The type of the node (e.g., 'file', 'folder', 'function', 'api').
 */
function addNode(id, label, type) {
    let shape = "box";
    let color = "black";

    if (type === "file") {
        shape = "ellipse"; // Files are better represented as ellipses or boxes, not folders
        color = "lightblue";
    } else if (type === "folder") {
        shape = "folder";
        color = "gray";
    } else if (type === "function") {
        shape = "ellipse";
        color = "palegreen";
    } else if (type === "module") {
        shape = "component";
        color = "orange";
    } else if (type === "api") {
        shape = "note";
        color = "tomato";
    }

    // DOT language format: "nodeId" [label="displayLabel", shape="box", color="red"];
    // Quoting IDs and labels to handle special characters.
    nodes.add(`  "${id}" [label="${label}", shape="${shape}", color="${color}", style=filled];`);
}

/**
 * Adds a directed edge between two nodes in the graph.
 * @param {string} from - The ID of the source node.
 * @param {string} to - The ID of the target node.
 * @param {string} label - The label for the edge.
 */
function addEdge(from, to, label) {
    // DOT language format: "fromNode" -> "toNode" [label="edgeLabel"];
    edges.add(`  "${from}" -> "${to}" [label="${label}"];`);
}

/**
 * Checks if an import path is for a local file or component.
 * @param {string} importPath - The import path string (e.g., './utils', '../components/Button').
 * @returns {boolean}
 */
function isFileOrComponentImport(importPath) {
    return importPath.startsWith("./") || importPath.startsWith("../");
}

/**
 * A filter to avoid graphing generic, uninteresting API calls.
 * @param {string} apiName - The name of the API being called (e.g., 'axios.get').
 * @returns {boolean}
 */
function isMeaningfulApiCall(apiName) {
    return apiName && apiName.startsWith("axios.");
}

/**
 * Creates nodes for each part of a file's path and connects them to show hierarchy.
 * @param {string} fileLabel - The full relative path of the file (e.g., 'src/api/user.js').
 */
function addFolderHierarchy(fileLabel) {
    const parts = fileLabel.split("/");
    let parent = null;
    let currentPath = "";

    // Iterate through the path parts (folders), but not the filename itself.
    for (let i = 0; i < parts.length - 1; i++) {
        currentPath = currentPath ? `${currentPath}/${parts[i]}` : parts[i];
        addNode(currentPath, parts[i], "folder");
        if (parent) {
            addEdge(parent, currentPath, "contains");
        }
        parent = currentPath;
    }

    // Link the last folder to the file.
    if (parent) {
        addEdge(parent, fileLabel, "contains");
    }
}


/**
 * Processes a single AST JSON file to extract nodes and edges.
 * @param {object} astWrapper - The parsed JSON object from the AST file.
 * @param {string} fileLabel - The unique label/ID for the file being processed.
 */
function processASTFile(astWrapper, fileLabel) {
    // Add file node and the folder structure leading to it.
    // Use the filename itself as the display label for the file node.
    const fileName = fileLabel.split('/').pop();
    addNode(fileLabel, fileName, "file");
    addFolderHierarchy(fileLabel);

    // --- Process Imports ---
    const imports = astWrapper.imports || astWrapper.metadata?.imports || [];
    for (const mod of imports) {
        const source = (typeof mod === 'string') ? mod : mod.source;
        if (source && isFileOrComponentImport(source)) {
            // Note: We don't resolve the relative path here, we just represent the import as written.
            addNode(source, source, "module");
            addEdge(fileLabel, source, "imports");
        }
    }

    // --- Process Function Definitions ---
    // Using a Set to avoid adding the same function node multiple times.
    const definedFunctions = new Set();
    const functions = astWrapper.functions || astWrapper.metadata?.functions || [];
    for (const fn of functions) {
        if (fn && fn !== "anonymous" && !definedFunctions.has(fn)) {
            const fnId = `${fileLabel}::${fn}`;
            addNode(fnId, fn, "function");
            addEdge(fileLabel, fnId, "defines");
            definedFunctions.add(fn);
        }
    }

    // --- Process Axios Calls ---
    const axiosCalls = astWrapper.axiosCalls || astWrapper.metadata?.axiosCalls || [];
    for (const call of axiosCalls) {
        if (call.method && call.endpoint) {
            const functionName = call.function || "anonymous";
            const fnId = `${fileLabel}::${functionName}`;
            
            // Add function node if it's anonymous or wasn't in the main function list.
            // A Set ensures it's only added once.
            if (!definedFunctions.has(functionName)) {
                addNode(fnId, functionName, "function");
                addEdge(fileLabel, fnId, "defines"); // Link anonymous/unlisted function to its file
                definedFunctions.add(functionName);
            }
            
            const apiNodeId = `axios.${call.method}('${call.endpoint}')`;
            const apiLabel = `${call.method.toUpperCase()}: ${call.endpoint}`;
            addNode(apiNodeId, apiLabel, "api");
            addEdge(fnId, apiNodeId, "axios call");
        }
    }
    
    // --- Process Generic API Calls (if different from Axios) ---
    const apiCalls = astWrapper.apiCalls || astWrapper.metadata?.apiCalls || [];
    for (const call of apiCalls) {
        // This example only looks for 'axios.*', but you could expand this.
        if (isMeaningfulApiCall(call.api) && call.endpoint) {
             const functionName = call.function || "anonymous";
             const fnId = `${fileLabel}::${functionName}`;
            
            if (!definedFunctions.has(functionName)) {
                addNode(fnId, functionName, "function");
                addEdge(fileLabel, fnId, "defines");
                definedFunctions.add(functionName);
            }
            
            const apiNodeId = `${call.api}('${call.endpoint}')`;
            const apiLabel = `${call.api}: ${call.endpoint}`;
            addNode(apiNodeId, apiLabel, "api");
            addEdge(fnId, apiNodeId, "api call");
        }
    }
}

/**
 * Recursively reads a directory to find and process all AST .json files.
 * @param {string} dir - The directory to read.
 * @param {string} base - The current relative path from the root `astDir`.
 */
function readASTFiles(dir, base = "") {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        const relPath = base ? `${base}/${entry.name}` : entry.name;

        if (entry.isDirectory()) {
            readASTFiles(fullPath, relPath);
        } else if (entry.isFile() && entry.name.endsWith(".json")) {
            try {
                const astWrapper = JSON.parse(fs.readFileSync(fullPath, "utf-8"));
                // Ensure consistent path separators (/)
                const fileLabel = relPath.replace(/\\/g, "/");
                processASTFile(astWrapper, fileLabel);
            } catch (err) {
                console.error(`Failed to parse or process ${fullPath}:`, err.message);
            }
        }
    }
}

/**
 * Generates the final .dot file from the collected nodes and edges.
 */
function generateDotFile() {
    // Using a template literal for cleaner multiline string construction.
    const dotContent = `
digraph Dependencies {
  rankdir="LR"; // Left-to-Right layout
  node [style=filled];
  
  // --- Nodes ---
${[...nodes].join("\n")}

  // --- Edges ---
${[...edges].join("\n")}
}
`;
    fs.writeFileSync(dotFilePath, dotContent.trim(), "utf-8");
    console.log(`✅ DOT file generated at ${dotFilePath}`);
}

// --- Main Execution ---
console.log("Starting AST analysis...");
readASTFiles(astDir);
generateDotFile();