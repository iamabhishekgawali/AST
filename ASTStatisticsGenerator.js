// To run this script:
// 1. First, generate the ASTs using the previous script.
// 2. Make sure the ASTs are in a directory (e.g., 'JavascriptAST').
// 3. Execute this script from your terminal, passing the path to the AST directory:
//    node analyze.js ./JavascriptAST
// 4. A file named 'analysis_report.json' will be created in the current directory.

const fs = require('fs');
const path = require('path');

// --- Helper Functions for Analysis ---

/**
 * Traverses the AST to find all nodes of a specific type.
 * @param {object} node - The current AST node to start from.
 * @param {string} type - The node type to find (e.g., 'function_declaration').
 * @returns {object[]} An array of nodes that match the type.
 */
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
 * Calculates the cyclomatic complexity of a function node.
 * @param {object} functionNode - The AST node of a function.
 * @returns {number} The cyclomatic complexity score.
 */
function calculateCyclomaticComplexity(functionNode) {
    let complexity = 1;
    const branchingTypes = [
        'if_statement', 'for_statement', 'while_statement', 'case_statement',
        'catch_clause', 'ternary_expression'
    ];
    
    findNodesByType(functionNode, 'binary_expression').forEach(node => {
        if (node.children.some(c => c.type === '&&' || c.type === '||')) {
            complexity++;
        }
    });

    branchingTypes.forEach(type => {
        complexity += findNodesByType(functionNode, type).length;
    });

    return complexity;
}

/**
 * Analyzes a single AST file and aggregates statistics.
 * @param {string} filePath - Path to the AST JSON file.
 * @param {object} stats - The global statistics object to update.
 */
function analyzeAstFile(filePath, stats) {
    const jsonContent = fs.readFileSync(filePath, 'utf8');
    const ast = JSON.parse(jsonContent);
    if (!ast) return;

    // --- 1. Code Composition & Complexity ---
    stats.composition.fileCount++;
    const linesOfCode = ast.endPosition.row - ast.startPosition.row + 1;
    stats.composition.totalLinesOfCode += linesOfCode;
    stats.composition.linesOfCodePerFile[filePath] = linesOfCode;

    const functions = findNodesByType(ast, 'function_declaration').concat(findNodesByType(ast, 'arrow_function'), findNodesByType(ast, 'method_definition'));
    stats.composition.functionCount += functions.length;
    stats.composition.classCount += findNodesByType(ast, 'class_declaration').length;
    
    const comments = findNodesByType(ast, 'comment');
    stats.composition.totalComments += comments.length;
    
    let maxDepth = 0;
    function getDepth(node, depth) {
        if (!node) return;
        maxDepth = Math.max(maxDepth, depth);
        if(node.children) node.children.forEach(child => getDepth(child, depth + 1));
    }
    getDepth(ast, 0);
    stats.complexity.maxNestingDepth = Math.max(stats.complexity.maxNestingDepth, maxDepth);

    let totalComplexity = 0;
    for (const func of functions) {
        totalComplexity += calculateCyclomaticComplexity(func);
    }
    stats.complexity.totalCyclomatic += totalComplexity;
    
    // --- 2. Dependency Analysis ---
    const imports = findNodesByType(ast, 'import_statement');
    stats.dependencies.importCount += imports.length;
    for (const imp of imports) {
        const sourceNode = imp.children.find(c => c.type === 'string');
        if (sourceNode) {
            const source = sourceNode.text.replace(/['"]/g, '');
            stats.dependencies.importFrequency[source] = (stats.dependencies.importFrequency[source] || 0) + 1;
            if (source.startsWith('.') || source.startsWith('@/')) {
                stats.dependencies.internalImports++;
            } else {
                stats.dependencies.externalImports++;
            }
             // Check for cloud SDKs within dependency analysis
            if (source.includes('@aws-sdk')) stats.infra.cloudSDKs.add('AWS');
            if (source.includes('@google-cloud')) stats.infra.cloudSDKs.add('Google Cloud');
            if (source.includes('firebase')) stats.infra.cloudSDKs.add('Firebase');
        }
    }

    // --- 3. API and Service Usage ---
    const apiCallKeywords = ['fetch', 'axios', 'http', 'https'];
    const callExpressions = findNodesByType(ast, 'call_expression');
    for (const call of callExpressions) {
         if (apiCallKeywords.some(kw => call.text.toLowerCase().includes(kw))) {
            stats.api.networkCallCount++;
        }
         // React Hook Detection
        const identifier = call.children[0]?.text;
        if (identifier && stats.reactSpecifics.hooks[identifier] !== undefined) {
            stats.reactSpecifics.hooks[identifier]++;
        }
    }
    const hardcodedUrlRegex = /https?:\/\/[^\s/$.?#].[^\s]*/gi;
    findNodesByType(ast, 'string').forEach(node => {
        const matches = node.text.match(hardcodedUrlRegex);
        if(matches){
            stats.api.hardcodedUrls.push(...matches);
        }
    });
    stats.api.fileIOCount += findNodesByType(ast, 'call_expression').filter(c => c.text.startsWith('fs.')).length;
    
    // --- 4. Code Quality & Maintainability ---
    stats.quality.tryCatchCount += findNodesByType(ast, 'try_statement').length;
    for (const comment of comments) {
        if (comment.text.toLowerCase().includes('todo') || comment.text.toLowerCase().includes('fixme')) {
            stats.quality.todoFixmeCount++;
        }
    }
    if (filePath.includes('.test.') || filePath.includes('.spec.')) {
        stats.quality.testFileCount++;
    }

    // --- 5. Application Structure ---
    const dir = path.dirname(filePath).split(path.sep).pop() || 'root';
    stats.structure.moduleSize[dir] = (stats.structure.moduleSize[dir] || 0) + linesOfCode;
    
    // --- 6. Modern JS & Code Style ---
    findNodesByType(ast, 'lexical_declaration').forEach(node => {
        if (node.text.startsWith('const')) stats.modernFeatures.variableDeclarations.const++;
        if (node.text.startsWith('let')) stats.modernFeatures.variableDeclarations.let++;
    });
    stats.modernFeatures.variableDeclarations.var += findNodesByType(ast, 'variable_declaration').length;
    stats.modernFeatures.arrowFunctions += findNodesByType(ast, 'arrow_function').length;
    stats.modernFeatures.templateLiterals += findNodesByType(ast, 'template_string').length;
    stats.modernFeatures.destructuringAssignments += findNodesByType(ast, 'object_pattern').length + findNodesByType(ast, 'array_pattern').length;
    stats.modernFeatures.spreadOperators += findNodesByType(ast, 'spread_element').length;
    
    // --- 7. Framework Specifics (React & Angular) ---
    const classDeclarations = findNodesByType(ast, 'class_declaration');
    for (const classNode of classDeclarations) {
        if (classNode.children.some(c => c.type === 'class_heritage' && c.text.includes('Component'))) {
            stats.reactSpecifics.classComponents++;
        }
        if (classNode.children.some(c => c.type === 'decorator' && c.text.startsWith('@Component'))) {
            stats.angularSpecifics.components++;
        }
    }
    if(findNodesByType(ast, 'jsx_element').length > 0 && !classDeclarations.some(c => c.children.some(child => child.type === 'class_heritage' && child.text.includes('Component')))){
         stats.reactSpecifics.functionalComponents++;
    }

    // --- 8. Infrastructure & Security ---
    findNodesByType(ast, 'member_expression').forEach(node => {
        if (node.text.startsWith('process.env')) {
            stats.infra.environmentVariables.add(node.text);
        }
    });
    findNodesByType(ast, 'jsx_attribute').forEach(attr => {
        if (attr.children[0]?.text === 'dangerouslySetInnerHTML') {
            stats.security.dangerouslySetInnerHTML++;
        }
        if (attr.children.some(c => c.type === 'jsx_expression' && findNodesByType(c, 'arrow_function').length > 0)) {
            stats.security.anonymousFuncInProps++;
        }
    });
}

// --- Main Execution ---
function main(astDir) {
    if (!fs.existsSync(astDir)) {
        console.error(`Error: Directory not found at '${astDir}'`);
        return;
    }

    const stats = {
        composition: { fileCount: 0, functionCount: 0, classCount: 0, totalLinesOfCode: 0, totalComments: 0, linesOfCodePerFile: {} },
        complexity: { maxNestingDepth: 0, totalCyclomatic: 0 },
        dependencies: { importCount: 0, internalImports: 0, externalImports: 0, importFrequency: {} },
        api: { networkCallCount: 0, fileIOCount: 0, hardcodedUrls: [] },
        quality: { todoFixmeCount: 0, tryCatchCount: 0, testFileCount: 0 },
        structure: { moduleSize: {} },
        modernFeatures: {
            variableDeclarations: { const: 0, let: 0, var: 0 },
            arrowFunctions: 0,
            templateLiterals: 0,
            destructuringAssignments: 0,
            spreadOperators: 0,
        },
        reactSpecifics: {
            classComponents: 0,
            functionalComponents: 0,
            hooks: { useState: 0, useEffect: 0, useContext: 0, useReducer: 0, useCallback: 0, useMemo: 0, useRef: 0 },
        },
        angularSpecifics: {
            components: 0,
        },
        infra: {
            environmentVariables: new Set(),
            cloudSDKs: new Set(),
        },
        security: {
            dangerouslySetInnerHTML: 0,
            anonymousFuncInProps: 0,
        }
    };

    function processDirectory(directory) {
        const files = fs.readdirSync(directory, { withFileTypes: true });
        for (const file of files) {
            const fullPath = path.join(directory, file.name);
            if (file.isDirectory()) {
                processDirectory(fullPath);
            } else if (path.extname(file.name) === '.json') {
                analyzeAstFile(fullPath, stats);
            }
        }
    }

    processDirectory(astDir);
    saveReportAsJson(stats);
}

/**
 * Saves the final statistics report to a JSON file.
 * @param {object} stats - The fully aggregated statistics object.
 */
function saveReportAsJson(stats) {
    // Convert sets to arrays for JSON serialization
    stats.infra.environmentVariables = Array.from(stats.infra.environmentVariables);
    stats.infra.cloudSDKs = Array.from(stats.infra.cloudSDKs);
    const externalDeps = Object.keys(stats.dependencies.importFrequency).filter(k => !k.startsWith('.') && !k.startsWith('@/'));

    const report = {
        "Code Composition & Complexity": {
            "Number of files": stats.composition.fileCount,
            "Total lines of code": stats.composition.totalLinesOfCode,
            "Number of functions": stats.composition.functionCount,
            "Number of classes": stats.composition.classCount,
            "Maximum nesting depth": stats.complexity.maxNestingDepth,
            "Total cyclomatic complexity": stats.complexity.totalCyclomatic,
            "Average cyclomatic complexity": parseFloat((stats.complexity.totalCyclomatic / (stats.composition.functionCount || 1)).toFixed(2)),
            "Total number of comments": stats.composition.totalComments,
            "Comment-to-code ratio": parseFloat((stats.composition.totalComments / (stats.composition.totalLinesOfCode || 1)).toFixed(3))
        },
        "Dependency Analysis": {
            "Number of import statements": stats.dependencies.importCount,
            "Types of imports (internal vs. external)": `${stats.dependencies.internalImports} vs. ${stats.dependencies.externalImports}`,
            "Third-party vs. in-house code ratio": parseFloat((stats.dependencies.externalImports / (stats.dependencies.importCount || 1)).toFixed(2)),
            "List of direct dependencies": externalDeps,
            "Import frequency by module/library": stats.dependencies.importFrequency
        },
        "API and Service Usage": {
            "Total number of network/API calls (heuristic)": stats.api.networkCallCount,
            "Total number of file I/O operations": stats.api.fileIOCount,
            "List and count of hardcoded URLs": {
                count: stats.api.hardcodedUrls.length,
                urls: stats.api.hardcodedUrls
            }
        },
        "Code Quality & Maintainability": {
            "Number of TODO / FIXME comments": stats.quality.todoFixmeCount,
            "Number of exception handling blocks (try/catch)": stats.quality.tryCatchCount,
            "Number of test files": stats.quality.testFileCount
        },
        "Application Structure": {
            "Number of modules/packages": Object.keys(stats.structure.moduleSize).length,
            "Size of each module/package (in lines of code)": stats.structure.moduleSize
        },
        "Modern Javascript Usage": stats.modernFeatures,
        "Framework Specifics": {
            "React": stats.reactSpecifics,
            "Angular": stats.angularSpecifics
        },
        "Infrastructure & Security": {
            "Environment Variables Accessed": stats.infra.environmentVariables,
            "Cloud SDKs Detected": stats.infra.cloudSDKs,
            "Use of dangerouslySetInnerHTML": stats.security.dangerouslySetInnerHTML,
            "Anonymous Functions in Props": stats.security.anonymousFuncInProps
        },
        "Unsupported or Partially Supported Metrics": {
            "Test coverage": "N/A from AST alone; needs runtime/test suite execution"
        }
    };

    const outputFilePath = path.join(process.cwd(), 'analysis_report.json');
    try {
        fs.writeFileSync(outputFilePath, JSON.stringify(report, null, 2));
        console.log(`\n✅ Successfully saved analysis report to: ${outputFilePath}`);
    } catch (e) {
        console.error(`\n❌ Failed to write report to file. Reason: ${e.message}`);
    }
}


// --- Entry Point ---
const astDirectory = process.argv[2];
if (!astDirectory) {
    console.error("Please provide the path to the directory containing the AST JSON files.");
    console.log("Usage: node analyze.js <path-to-ast-directory>");
} else {
    main(astDirectory);
}
