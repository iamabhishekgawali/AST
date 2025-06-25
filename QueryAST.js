const fs = require('fs');
const path = require('path');

// --- Helper Functions ---

function findNodesOfType(node, type) {
    let nodes = [];
    if (!node) return nodes;
    if (node.type === type) nodes.push(node);
    if (node.children) {
        for (const child of node.children) {
            nodes.push(...findNodesOfType(child, type));
        }
    }
    return nodes;
}

function calculateNestingDepth(node) {
    const controlStructures = ['if_statement', 'for_statement', 'while_statement', 'switch_statement'];
    let maxChildDepth = 0;
    if (node.children) {
        for (const child of node.children) {
            maxChildDepth = Math.max(maxChildDepth, calculateNestingDepth(child));
        }
    }
    return (controlStructures.includes(node.type) ? 1 : 0) + maxChildDepth;
}

function calculateCyclomaticComplexity(functionNode) {
    let complexity = 1;
    const decisionTypes = ['if_statement', 'for_statement', 'while_statement', 'case_statement', 'conditional_expression', 'binary_expression'];
    const logicalOperators = ['&&', '||'];
    
    findNodesOfType(functionNode, 'binary_expression').forEach(node => {
        if(logicalOperators.includes(node.children[1]?.text)) complexity++;
    });
    findNodesOfType(functionNode, 'if_statement').forEach(() => complexity++);
    findNodesOfType(functionNode, 'for_statement').forEach(() => complexity++);
    findNodesOfType(functionNode, 'while_statement').forEach(() => complexity++);
    findNodesOfType(functionNode, 'case_statement').forEach(() => complexity++);
    findNodesOfType(functionNode, 'conditional_expression').forEach(() => complexity++);

    return complexity;
}

// --- Main Analysis Logic ---

function analyzeFile(ast) {
    const metrics = {};
    const functions = findNodesOfType(ast, 'function_declaration').concat(findNodesOfType(ast, 'arrow_function'));
    const classes = findNodesOfType(ast, 'class_declaration');
    const comments = findNodesOfType(ast, 'comment');
    const imports = findNodesOfType(ast, 'import_statement');
    const calls = findNodesOfType(ast, 'call_expression');
    const strings = findNodesOfType(ast, 'string');

    // Per-File Metrics
    metrics.linesOfCode = ast.endPosition.row - ast.startPosition.row + 1;
    metrics.functionCount = functions.length;
    metrics.classCount = classes.length;
    metrics.commentCount = comments.length;
    metrics.nestingDepth = Math.max(0, ...functions.map(f => calculateNestingDepth(f)));
    metrics.cyclomaticComplexity = functions.reduce((sum, func) => sum + calculateCyclomaticComplexity(func), 0);
    metrics.imports = imports.map(node => node.children.find(c => c.type === 'string')?.text.replace(/['"]/g, '')).filter(Boolean);
    metrics.networkCalls = calls.filter(c => c.text.match(/(fetch|axios|requests)/)).length;
    metrics.apiEndpointDefinitions = findNodesOfType(ast, 'jsx_opening_element').filter(node => node.children[0]?.text === 'Route').length;
    metrics.fileIoOperations = calls.filter(c => c.text.match(/(fs.readFile|fs.writeFile)/)).length;
    metrics.hardcodedUrlsAndIPs = strings.filter(s => s.text.match(/https?:\/\/|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/)).map(s => s.text);
    metrics.todosAndFixmes = comments.filter(c => c.text.match(/(TODO|FIXME)/i)).length;
    metrics.deprecatedApiCalls = calls.filter(c => ['componentWillMount', 'componentWillReceiveProps'].some(api => c.text.startsWith(api))).length;
    metrics.exceptionHandlers = findNodesOfType(ast, 'try_statement').length;
    metrics.userInputHandlers = calls.filter(c => c.text.match(/(request.body|request.query|input\()/)).length;
    metrics.cryptoUsage = calls.filter(c => c.text.match(/crypto/)).length;
    metrics.permissionChecks = calls.filter(c => ['checkPermissions', 'requireAuth'].some(api => c.text.startsWith(api))).length;
    
    return metrics;
}

function aggregateReport(allFileMetrics) {
    const report = {
        codeComposition: {
            numberOfFiles: 0,
            numberOfClasses: 0,
            numberOfFunctions: 0,
            linesOfCodePerFile: {},
            totalLinesOfCode: 0,
            maxNestingDepth: 0,
            totalCyclomaticComplexity: 0,
            totalCommentCount: 0,
            averageCyclomaticComplexity: 0,
            commentToCodeRatio: 0,
        },
        dependencyAnalysis: {
            importsByType: { internal: 0, external: 0 },
            importFrequency: {},
            directDependencies: [],
            thirdPartyVsInHouseRatio: 0
        },
        apiAndServiceUsage: {
            totalNetworkCalls: 0,
            totalApiEndpointsDefined: 0,
            totalFileIoOperations: 0,
            listOfHardcodedUrlsAndIPs: [],
        },
        qualityAndMaintainability: {
            totalTodosAndFixmes: 0,
            totalDeprecatedApiCalls: 0,
            totalExceptionHandlers: 0
        },
        applicationStructure: {
            numberOfModules: 0,
            distributionOfCodeByLayer: {},
            sizeOfEachModuleByLines: {}
        },
        security: {
            totalUserInputHandlers: 0,
            totalCryptoUsage: 0,
            totalPermissionChecks: 0,
        },
        unsupportedMetrics: {
            testCoverage: "N/A - Cannot be determined via static analysis. Requires running a test suite."
        }
    };

    for (const [filePath, metrics] of Object.entries(allFileMetrics)) {
        // Code Composition
        report.codeComposition.numberOfFiles++;
        report.codeComposition.numberOfClasses += metrics.classCount;
        report.codeComposition.numberOfFunctions += metrics.functionCount;
        report.codeComposition.linesOfCodePerFile[filePath] = metrics.linesOfCode;
        report.codeComposition.totalLinesOfCode += metrics.linesOfCode;
        report.codeComposition.maxNestingDepth = Math.max(report.codeComposition.maxNestingDepth, metrics.nestingDepth);
        report.codeComposition.totalCyclomaticComplexity += metrics.cyclomaticComplexity;
        report.codeComposition.totalCommentCount += metrics.commentCount;
        
        // Dependency Analysis
        metrics.imports.forEach(imp => {
            if (imp.startsWith('.')) {
                report.dependencyAnalysis.importsByType.internal++;
            } else {
                report.dependencyAnalysis.importsByType.external++;
            }
            report.dependencyAnalysis.importFrequency[imp] = (report.dependencyAnalysis.importFrequency[imp] || 0) + 1;
        });

        // API and Service Usage
        report.apiAndServiceUsage.totalNetworkCalls += metrics.networkCalls;
        report.apiAndServiceUsage.totalApiEndpointsDefined += metrics.apiEndpointDefinitions;
        report.apiAndServiceUsage.totalFileIoOperations += metrics.fileIoOperations;
        report.apiAndServiceUsage.listOfHardcodedUrlsAndIPs.push(...metrics.hardcodedUrlsAndIPs);

        // Quality and Maintainability
        report.qualityAndMaintainability.totalTodosAndFixmes += metrics.todosAndFixmes;
        report.qualityAndMaintainability.totalDeprecatedApiCalls += metrics.deprecatedApiCalls;
        report.qualityAndMaintainability.totalExceptionHandlers += metrics.exceptionHandlers;
        
        // Application Structure
        const modulePath = path.dirname(filePath);
        if (modulePath !== '.') {
           report.applicationStructure.sizeOfEachModuleByLines[modulePath] = (report.applicationStructure.sizeOfEachModuleByLines[modulePath] || 0) + metrics.linesOfCode;
           const layer = modulePath.split(path.sep)[0] || 'root';
           report.applicationStructure.distributionOfCodeByLayer[layer] = (report.applicationStructure.distributionOfCodeByLayer[layer] || 0) + 1;
        }

        // Security
        report.security.totalUserInputHandlers += metrics.userInputHandlers;
        report.security.totalCryptoUsage += metrics.cryptoUsage;
        report.security.totalPermissionChecks += metrics.permissionChecks;
    }

    // Final Calculations
    const comp = report.codeComposition;
    comp.averageCyclomaticComplexity = comp.numberOfFunctions > 0 ? comp.totalCyclomaticComplexity / comp.numberOfFunctions : 0;
    comp.commentToCodeRatio = comp.totalLinesOfCode > 0 ? comp.totalCommentCount / comp.totalLinesOfCode : 0;
    
    const deps = report.dependencyAnalysis;
    deps.directDependencies = Object.keys(deps.importFrequency);
    deps.thirdPartyVsInHouseRatio = deps.importsByType.internal > 0 ? deps.importsByType.external / deps.importsByType.internal : Infinity;

    report.applicationStructure.numberOfModules = Object.keys(report.applicationStructure.sizeOfEachModuleByLines).length;
    report.apiAndServiceUsage.listOfHardcodedUrlsAndIPs = [...new Set(report.apiAndServiceUsage.listOfHardcodedUrlsAndIPs)];

    return report;
}

function processDirectory(currentDir, baseDir) {
    let allMetrics = {};
    const entries = fs.readdirSync(currentDir, { withFileTypes: true });

    for (const entry of entries) {
        const fullPath = path.join(currentDir, entry.name);
        if (entry.isDirectory()) {
            Object.assign(allMetrics, processDirectory(fullPath, baseDir));
        } else if (path.extname(entry.name) === '.json') {
            const originalFilePath = path.relative(baseDir, fullPath).slice(0, -5);
            try {
                const ast = JSON.parse(fs.readFileSync(fullPath, 'utf8'));
                allMetrics[originalFilePath] = analyzeFile(ast);
            } catch (e) {
                console.error(`[ERROR] Failed to analyze ${fullPath}: ${e.message}`);
            }
        }
    }
    return allMetrics;
}

// --- Main Execution ---
const astDirectory = './ast_output';
const reportOutputFile = './analysis_report.json';

if (!fs.existsSync(astDirectory)) {
    console.error(`[ERROR] AST output directory not found at '${astDirectory}'.`);
} else {
    console.log(`Analyzing all AST files from '${astDirectory}'...`);
    const allFileMetrics = processDirectory(astDirectory, astDirectory);
    console.log("Aggregating data into a single project report...");
    const finalReport = aggregateReport(allFileMetrics);
    
    fs.writeFileSync(reportOutputFile, JSON.stringify(finalReport, null, 2));
    console.log(`\n✅ DONE. A complete, single-file report has been saved to '${reportOutputFile}'`);
}
