/* Independent Khronos validator. Install pinned tools/rig/package-lock.json. */
'use strict';
const fs = require('fs');
const path = require('path');
const root = process.env.HATCH_GLTF_VALIDATOR_ROOT || path.join(__dirname, '../tools/rig/node_modules/gltf-validator');
const validator = require(root);
const filename = path.resolve(process.argv[2]);
const bytes = fs.readFileSync(filename);
const options = { uri:path.basename(filename), maxIssues:1000,
  externalResourceFunction: async (uri) => {
    if (/^(?:[a-z]+:|\/|\\)/i.test(uri) || uri.includes('\\')) throw new Error('Unsafe external URI');
    const candidate = path.resolve(path.dirname(filename), decodeURIComponent(uri));
    if (!candidate.startsWith(path.dirname(filename)+path.sep)) throw new Error('External resource escapes model directory');
    return new Uint8Array(fs.readFileSync(candidate));
  }
};
validator.validateBytes(new Uint8Array(bytes),options).then(report=>{
  process.stdout.write(JSON.stringify({validator:validator.version(),...report},null,2)+'\n');
  process.exitCode=report.issues.numErrors?1:0;
}).catch(error=>{process.stderr.write(String(error)+'\n');process.exitCode=2;});
