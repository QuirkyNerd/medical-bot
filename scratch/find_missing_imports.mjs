import fs from 'fs';
import path from 'path';

const HOOKS = ['useState', 'useEffect', 'useRef', 'useMemo', 'useCallback', 'useContext'];

function walk(dir) {
  let results = [];
  const list = fs.readdirSync(dir);
  for (const file of list) {
    const full = path.join(dir, file);
    const stat = fs.statSync(full);
    if (stat && stat.isDirectory()) {
      if (!full.includes('node_modules') && !full.includes('.next')) {
        results = results.concat(walk(full));
      }
    } else if (full.endsWith('.tsx') || full.endsWith('.ts')) {
      results.push(full);
    }
  }
  return results;
}

const files = walk('./web');
for (const file of files) {
  const content = fs.readFileSync(file, 'utf-8');
  let usedHooks = [];
  for (const hook of HOOKS) {
    if (new RegExp('\\\\b' + hook + '\\\\b').test(content)) {
      usedHooks.push(hook);
    }
  }
  
  if (usedHooks.length > 0) {
    let missingHooks = [];
    
    // Check if the hooks are imported
    for (const hook of usedHooks) {
      const importRegex = new RegExp('import\\\\s+.*\\\\b' + hook + '\\\\b.*\\\\s+from\\\\s+["\']react["\']');
      if (!importRegex.test(content)) {
        missingHooks.push(hook);
      }
    }
    
    let isMissingUseClient = !content.includes('"use client"') && !content.includes("'use client'");
    
    if (missingHooks.length > 0 || isMissingUseClient) {
      console.log('---');
      console.log('File:', file);
      if (missingHooks.length > 0) console.log('Missing imports:', missingHooks.join(', '));
      if (isMissingUseClient) console.log('Missing \"use client\"');
    }
  }
}
