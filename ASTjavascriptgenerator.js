// To run this script:
// 1. Make sure you have the necessary packages:
//    npm install tree-sitter tree-sitter-typescript
// 2. Execute the script from your terminal, passing the path to your project:
//    node your_script_name.js /path/to/your/react/project

const fs = require('fs');
const path = require('path');
const Parser = require('tree-sitter');
// Use the TypeScript grammar which supports JS, JSX, TS, and TSX
const TypeScript = require('tree-sitter-typescript').typescript;

/**
 * Creates a serializable, plain JavaScript object from a Tree-sitter node.
 * This is necessary because the original nodes have circular references,
 * which prevents them from being stringified to JSON directly.
 * @param {Parser.SyntaxNode} node - The Tree-sitter AST node.
 * @returns {object | null} A serializable object representation of the node, or null.
 */
function createSerializableNode(node) {
    if (!node) return null;

    // Create a plain object with the essential properties of the node.
    const serializableNode = {
        type: node.type,
        text: node.text,
        startPosition: node.startPosition,
        endPosition: node.endPosition,
        // Recursively serialize only the named children for a cleaner AST.
        children: node.namedChildren.map(createSerializableNode)
    };

    return serializableNode;
}


/**
 * Recursively finds and parses all relevant files in a project directory,
 * saving each Abstract Syntax Tree (AST) to a corresponding file in the output directory.
 * @param {string} dir - The directory to start searching from.
 * @param {string} baseProjectDir - The root directory of the user's project to calculate relative paths.
 * @param {string} outputDir - The root directory to save AST files.
 * @param {Parser} parser - The Tree-sitter parser instance.
 * @returns {number} The count of files successfully parsed.
 */
function parseAndSaveAsts(dir, baseProjectDir, outputDir, parser) {
    let fileCount = 0;
    // Define the file extensions to look for.
    const reactExtensions = ['.js', '.jsx', '.ts', '.tsx'];
    // Define directories to ignore to speed up parsing and avoid unnecessary files.
    const ignoredDirs = ['node_modules', '.git', 'build', 'dist', 'JavascriptAST'];

    let entries;
    try {
        // Get all entries in the current directory.
        entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch (e) {
        console.error(`[ERROR] Could not read directory: ${dir}. Skipping. Reason: ${e.message}`);
        return 0; // Skip this directory if it can't be read
    }


    for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory()) {
            // If it's a directory, ignore it if it's in our ignore list, otherwise recurse.
            if (!ignoredDirs.includes(entry.name)) {
                fileCount += parseAndSaveAsts(fullPath, baseProjectDir, outputDir, parser);
            }
        } else if (reactExtensions.includes(path.extname(entry.name))) {
            // If it's a file with a valid React/JS/TS extension, parse it.
            try {
                const code = fs.readFileSync(fullPath, 'utf8');
                const tree = parser.parse(code);

                // Create a serializable version of the AST to prepare for JSON conversion.
                const serializableAst = createSerializableNode(tree.rootNode);

                // Determine the output path for the AST JSON file, preserving the folder structure.
                const relativePath = path.relative(baseProjectDir, fullPath);
                const outputFilePath = path.join(outputDir, `${relativePath}.json`);
                const outputFileDir = path.dirname(outputFilePath);

                // Ensure the output directory for this specific file exists.
                fs.mkdirSync(outputFileDir, { recursive: true });
                
                // Write the serializable AST to the JSON file.
                fs.writeFileSync(outputFilePath, JSON.stringify(serializableAst, null, 2));
                
                console.log(`[SUCCESS] Saved AST for: ${fullPath} -> ${outputFilePath}`);
                fileCount++;
            } catch (e) {
                // Log an error if a specific file fails to be processed.
                console.error(`[FAILED] Could not process ${fullPath}. Reason: ${e.message}`);
            }
        }
    }
    return fileCount;
}

// --- Main Execution ---
console.log("Setting up Node.js AST parser...");

// 1. Initialize the parser and set the language to TypeScript (which handles JSX/TSX)
const parser = new Parser();
parser.setLanguage(TypeScript);

// 2. Get the project directory from command-line arguments. Default to "." if not provided.
const projectDirectoryArg = process.argv[2];
if (!projectDirectoryArg) {
    console.warn("No project directory provided. Defaulting to current directory.");
    console.info("Usage: node your_script_name.js <path-to-your-project>");
}
const projectDirectory = path.resolve(projectDirectoryArg || "."); // Use resolved absolute path

// 3. Define the output directory to be in the current working directory.
const outputDirectory = path.join(process.cwd(), "JavascriptAST");

// 4. Check if the provided project directory exists.
if (!fs.existsSync(projectDirectory) || !fs.lstatSync(projectDirectory).isDirectory()) {
    console.error(`Error: The specified directory does not exist or is not a directory: '${projectDirectory}'`);
    process.exit(1); // Exit with an error code
}

// 5. Create the main output directory if it doesn't exist.
if (!fs.existsSync(outputDirectory)) {
    fs.mkdirSync(outputDirectory);
}

console.log(`\nStarting AST parsing for project at: '${projectDirectory}'`);
console.log(`AST files will be saved in: '${outputDirectory}'\n`);


// 6. Run the parsing and saving process.
const totalFilesParsed = parseAndSaveAsts(projectDirectory, projectDirectory, outputDirectory, parser);

// 7. Display a final summary.
if (totalFilesParsed > 0) {
    console.log(`\n✅ Successfully generated and saved ASTs for ${totalFilesParsed} files.`);
} else {
    console.log("\n⚠️ No relevant files (.js, .jsx, .ts, .tsx) were found to parse in the specified directory.");
}
