// To run this script:
// 1. Generate ASTs for any language.
// 2. Use the corresponding advanced configuration file.
// 3. Execute from your terminal:
//    node Universal-AST-Analyzer-V2.js ./JavascriptAST ./javascript.advanced.config.json
//    node Universal-AST-Analyzer-V2.js ./PythonAST ./python.advanced.config.json

const fs = require('fs');
const path = require('path');

// --- Helper Functions ---

function getConfigValue(config, keyPath, defaultValue = undefined) {
    const value = keyPath.split('.').reduce((obj, key) => (obj && obj[key] !== undefined) ? obj[key] : undefined, config);
    return value !== undefined ? value : defaultValue;
}

function findNodesByType(node, type) {
    let nodes = [];
    if (!node) return nodes;
    if (node.type === type) {
        nodes.push(node);
    }
    if (node.children && node.children.length > 0) {
        for (const child of node.children) {
            nodes = nodes.concat(findNodesByType(child, type));
        }
    }
    return nodes;
}

/**
 * Extracts a specific value from a node by following a path query from the config.
 * @param {object} node - The starting AST node.
 * @param {object} query - The path query object from the config.
 * @returns {string|null} The extracted text value or null.
 */
function extractValueByPath(node, query) {
    if (!query || !node) return null;
    let currentNode = node;
    for (const step of query.path) {
        const childNode = (currentNode.children || []).find(c => c.type === step.type && (!step.textMatch || c.text.includes(step.textMatch)));
        if (!childNode) return null;
        currentNode = childNode;
    }
    return currentNode.text.replace(/['"]/g, '');
}

/**
 * Analyzes a single AST file and aggregates statistics.
 */
function analyzeAstFile(filePath, stats, langConfig) {
    const jsonContent = fs.readFileSync(filePath, 'utf8');
    const ast = JSON.parse(jsonContent);
    if (!ast) return;

    // --- 1. Code Composition ---
    stats.composition.fileCount++;
    if (ast.startPosition && ast.endPosition) {
        stats.composition.totalLinesOfCode += ast.endPosition.row - ast.startPosition.row + 1;
    }
    const functionTypes = getConfigValue(langConfig, 'selectors.function', []);
    let functions = [];
    functionTypes.forEach(type => functions = functions.concat(findNodesByType(ast, type)));
    stats.composition.functionCount += functions.length;

    const classTypes = getConfigValue(langConfig, 'selectors.class', []);
    classTypes.forEach(type => stats.composition.classCount += findNodesByType(ast, type).length);
    
    const commentTypes = getConfigValue(langConfig, 'selectors.comment', []);
    let comments = [];
    commentTypes.forEach(type => comments = comments.concat(findNodesByType(ast, type)));
    stats.composition.totalComments += comments.length;

    // --- 2. Dependency Analysis ---
    const importSelectors = getConfigValue(langConfig, 'selectors.import', []);
    for (const selector of importSelectors) {
        const importNodes = findNodesByType(ast, selector.type);
        for (const node of importNodes) {
            stats.dependencies.importCount++;
            const depName = extractValueByPath(node, selector.source);
            if (depName) {
                stats.dependencies.importFrequency[depName] = (stats.dependencies.importFrequency[depName] || 0) + 1;
            }
        }
    }

    // --- 3. API, Database, and other Pattern-based Metrics ---
    const patternSelectors = getConfigValue(langConfig, 'selectors.patterns', {});
    for (const metricName in patternSelectors) {
        const selector = patternSelectors[metricName];
        const nodes = findNodesByType(ast, selector.type);
        for (const node of nodes) {
            
            // --- FIX STARTS HERE ---
            // Check if node.text exists before trying to call .includes() on it.
            if (node.text && node.text.includes(selector.textMatch)) {
            // --- FIX ENDS HERE ---

                stats.usage[metricName] = stats.usage[metricName] || { count: 0, list: [] };
                stats.usage[metricName].count++;
                const value = extractValueByPath(node, selector.value);
                if (value) {
                    stats.usage[metricName].list.push(value);
                }
            }
        }
    }
}

// --- Main Execution ---
function main(astDir, configPath) {
    if (!fs.existsSync(astDir) || !fs.existsSync(configPath)) {
        console.error("Error: AST directory or language configuration not found.");
        return;
    }
    const langConfig = JSON.parse(fs.readFileSync(configPath, 'utf8'));
    console.log(`Analyzing project with "${langConfig.language}" configuration...`);

    const stats = {
        composition: { fileCount: 0, functionCount: 0, classCount: 0, totalLinesOfCode: 0, totalComments: 0 },
        dependencies: { importCount: 0, importFrequency: {} },
        usage: {}
    };

    function processDirectory(directory) {
        const files = fs.readdirSync(directory, { withFileTypes: true });
        for (const file of files) {
            const fullPath = path.join(directory, file.name);
            file.isDirectory() ? processDirectory(fullPath) : (path.extname(file.name) === '.json' && analyzeAstFile(fullPath, stats, langConfig));
        }
    }

    processDirectory(astDir);
    saveReportAsJson(stats, langConfig);
}

/**
 * Saves the final statistics report to a JSON file.
 */
function saveReportAsJson(stats, langConfig) {
    const report = {
        "Code Composition": {
            "Number of files": stats.composition.fileCount,
            "Total lines of code": stats.composition.totalLinesOfCode,
            "Number of functions": stats.composition.functionCount,
            "Number of classes": stats.composition.classCount,
            "Total number of comments": stats.composition.totalComments,
        },
        "Dependency Analysis": {
            "Number of import statements": stats.dependencies.importCount,
            "List of direct dependencies": Object.keys(stats.dependencies.importFrequency),
            "Import frequency by module/library": stats.dependencies.importFrequency
        },
        "API and Service Usage": {},
        "Framework & Infrastructure": {}
    };

    // Populate usage stats
    for (const metricName in stats.usage) {
        report["API and Service Usage"][metricName] = {
            count: stats.usage[metricName].count,
            list: stats.usage[metricName].list
        };
    }
    
    // Populate framework and tech detection from dependencies
    const dependencyMaps = getConfigValue(langConfig, 'dependencyMaps', {});
    for (const mapType in dependencyMaps) {
        report["Framework & Infrastructure"][mapType] = [];
        const depMap = dependencyMaps[mapType];
        for (const dep in depMap) {
            if (stats.dependencies.importFrequency[dep]) {
                report["Framework & Infrastructure"][mapType].push(depMap[dep]);
            }
        }
    }

    const outputFilePath = path.join(process.cwd(), 'analysis_report.json');
    fs.writeFileSync(outputFilePath, JSON.stringify(report, null, 2));
    console.log(`\n✅ Successfully saved analysis report to: ${outputFilePath}`);
}

// --- Entry Point ---
const [,, astDirectory, configPath] = process.argv;
if (!astDirectory || !configPath) {
    console.log("Usage: node Universal-AST-Analyzer-V2.js <path-to-ast-directory> <path-to-config.json>");
} else {
    main(astDirectory, configPath);
}