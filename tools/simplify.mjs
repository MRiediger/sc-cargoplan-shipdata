// simplify.mjs - meshoptimizer 1.3.0 on a shell.bin (T7.4c-1). API: node_modules/meshoptimizer/meshopt_simplifier.d.ts.
// in.bin: uint32 vertexCount, uint32 triangleCount, float32 xyz * vc (metres), uint32 indices * 3tc.
// out.idx: uint32 triangleCount, uint32 indices * 3tc, into the input vertex buffer (simplify keeps the vertices).
// Methods: M1 = simplify with Prune; M2 = M1 + Permissive, then simplifySloppy where M1 stops above 110 % of target;
// PP = Prune + Permissive without sloppy (chosen in T7.4c-1); ref = like M1 with a tight error, the reference for the
// metrics. Errors are absolute (metres, ErrorAbsolute).
// Caveat: the docs describe Permissive for attribute seams only; these meshes carry positions alone, yet it lowers the
// triangle count at the same error (Ironclad 47.8 k -> 39.9 k at 0.5 %). Measured, not explained.
// Prints JSON: triangles, errorM, sloppy, ms.
import { readFileSync, writeFileSync, renameSync } from 'node:fs';
import { MeshoptSimplifier as S } from 'meshoptimizer';

const [input, output, targetArg, maxErrorArg, method] = process.argv.slice(2);
const maxError = Number(maxErrorArg);
let target = Number(targetArg);
if (!input || !output || !(target > 0) || !(maxError > 0) || !['M1', 'M2', 'PP', 'ref'].includes(method)) {
  console.error('usage: node simplify.mjs <in.bin> <out.idx> <targetTriangles> <maxErrorM> <M1|M2|PP|ref>');
  process.exit(2);
}

await S.ready;
const buf = readFileSync(input);
const view = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
const vc = view.getUint32(0, true), tc = view.getUint32(4, true);
// copies, so the typed arrays are aligned
const positions = new Float32Array(buf.buffer.slice(buf.byteOffset + 8, buf.byteOffset + 8 + 12 * vc));
const indices = new Uint32Array(buf.buffer.slice(buf.byteOffset + 8 + 12 * vc, buf.byteOffset + 8 + 12 * vc + 12 * tc));
target = Math.min(target, tc);   // simplify asserts target_index_count <= indices.length

const started = performance.now();
const flags = ['M2', 'PP'].includes(method) ? ['Prune', 'ErrorAbsolute', 'Permissive'] : ['Prune', 'ErrorAbsolute'];
let [result, error] = S.simplify(indices, positions, 3, target * 3, maxError, flags);
let sloppy = false;
if (method === 'M2' && result.length / 3 > 1.1 * target) {
  // simplifySloppy takes no flags: its error is relative to the mesh extent
  const scale = S.getScale(positions, 3);
  const [loose, relError] = S.simplifySloppy(result, positions, 3, null, target * 3, maxError / scale);
  result = loose;
  error = Math.max(error, relError * scale);
  sloppy = true;
}
const ms = Math.round(performance.now() - started);

const out = Buffer.alloc(4 + 4 * result.length);
out.writeUInt32LE(result.length / 3, 0);
Buffer.from(result.buffer, result.byteOffset, result.byteLength).copy(out, 4);
writeFileSync(output + '.tmp', out);
renameSync(output + '.tmp', output);
console.log(JSON.stringify({ triangles: result.length / 3, errorM: error, sloppy, ms }));
