const fs = require('fs');
const path = require('path');
const Parser = require('tree-sitter');
const JavaScript = require('tree-sitter-javascript');

/**
 * Creates a serializable, plain JavaScript object from a Tree-sitter node.
 * This is necessary because the original nodes have circular references.
 * @param {object} node - The Tree-sitter AST node.
 * @returns {object} A serializable object representation of the node.
 */
function createSerializableNode(node) {
    if (!node) return null;
    
    const serializableNode = {
        type: node.type,
        text: node.text,
        startPosition: node.startPosition,
        endPosition: node.endPosition,
        children: node.namedChildren.map(createSerializableNode) // Recursively serialize children
    };
    
    return serializableNode;
}


/**
 * Recursively finds and parses all relevant files in a React project directory,
 * saving each AST to a corresponding file in the output directory.
 * @param {string} dir - The directory to start searching from.
 * @param {string} outputDir - The root directory to save AST files.
 * @param {Parser} parser - The Tree-sitter parser instance.
 */
function parseAndSaveAsts(dir, outputDir, parser) {
    let fileCount = 0;
    const reactExtensions = ['.js', '.jsx', '.ts', '.tsx'];
    const ignoredDirs = ['node_modules', '.git', 'build', 'dist', 'ast_output']; // Also ignore our output dir

    // Get all entries in the current directory
    const entries = fs.readdirSync(dir, { withFileTypes: true });

    for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory()) {
            // If it's a directory, ignore it if it's in our ignore list, otherwise recurse
            if (!ignoredDirs.includes(entry.name)) {
                fileCount += parseAndSaveAsts(fullPath, outputDir, parser);
            }
        } else if (reactExtensions.includes(path.extname(entry.name))) {
            // If it's a file with a valid extension, parse it and save it
            try {
                const code = fs.readFileSync(fullPath, 'utf8');
                const tree = parser.parse(code);

                // Create a serializable version of the AST
                const serializableAst = createSerializableNode(tree.rootNode);

                // Determine the output path for the AST JSON file
                const relativePath = path.relative(process.cwd(), fullPath);
                const outputFilePath = path.join(outputDir, `${relativePath}.json`);
                const outputFileDir = path.dirname(outputFilePath);

                // Ensure the output directory for this file exists
                fs.mkdirSync(outputFileDir, { recursive: true });
                
                // Write the serializable AST to the JSON file
                fs.writeFileSync(outputFilePath, JSON.stringify(serializableAst, null, 2));
                
                console.log(`[SUCCESS] Saved AST for: ${fullPath} -> ${outputFilePath}`);
                fileCount++;
            } catch (e) {
                console.error(`[FAILED] Could not process ${fullPath}. Reason: ${e.message}`);
            }
        }
    }
    return fileCount;
}

// --- Main Execution ---
console.log("Setting up Node.js AST parser...");

// 1. Initialize the parser with the JavaScript grammar
const parser = new Parser();
parser.setLanguage(JavaScript);

// 2. Define the project and output directories
const projectDirectory = ".";
const outputDirectory = path.join(projectDirectory, "ast_output");

// 3. Create the main output directory if it doesn't exist
if (!fs.existsSync(outputDirectory)) {
    fs.mkdirSync(outputDirectory);
}

console.log(`Starting AST parsing for project at: '${path.resolve(projectDirectory)}'`);
console.log(`AST files will be saved in: '${path.resolve(outputDirectory)}'\n`);


// 4. Run the parsing and saving process
const totalFilesParsed = parseAndSaveAsts(projectDirectory, outputDirectory, parser);

// 5. Display a summary
if (totalFilesParsed > 0) {
    console.log(`\nSuccessfully generated and saved ASTs for ${totalFilesParsed} files.`);
} else {
    console.log("\nNo React files (.js, .jsx, .ts, .tsx) were found to parse.");
}
