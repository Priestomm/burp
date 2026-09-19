// Generates TypeScript types from the JSON Schemas exported by the Python pipeline
// (pipeline/schema/*.json, produced by `uv run python export_schema.py`).
import { readFile, writeFile } from 'node:fs/promises';
import { compile } from 'json-schema-to-typescript';

const schemaDir = new URL('../../pipeline/schema/', import.meta.url);
const outFile = new URL('../src/lib/types/generated.ts', import.meta.url);

async function readSchema(file) {
  return JSON.parse(await readFile(new URL(file, schemaDir), 'utf8'));
}

// Property titles would produce one type alias per field; minItems would produce tuples.
// Neither is useful in TypeScript, so both are dropped before compiling.
function simplify(node, isDefinition = false) {
  if (Array.isArray(node)) return node.map((item) => simplify(item));
  if (node === null || typeof node !== 'object') return node;
  const result = {};
  for (const [key, value] of Object.entries(node)) {
    if (key === 'title' && !isDefinition) continue;
    if (key === 'minItems') continue;
    result[key] = key === '$defs' ? simplifyDefinitions(value) : simplify(value);
  }
  return result;
}

function simplifyDefinitions(defs) {
  return Object.fromEntries(Object.entries(defs).map(([name, def]) => [name, simplify(def, true)]));
}

const ingredients = await readSchema('ingredients.schema.json');
const recipes = await readSchema('recipes.schema.json');

const root = {
  type: 'object',
  additionalProperties: false,
  properties: {
    ingredients: { type: 'array', items: { $ref: '#/$defs/Ingredient' } },
    recipes: { type: 'array', items: { $ref: '#/$defs/Recipe' } },
  },
  required: ['ingredients', 'recipes'],
  $defs: { ...ingredients.$defs, ...recipes.$defs },
};

const banner =
  '/* Generated from pipeline/schema/*.json by scripts/generate-types.mjs. Do not edit. */';
const types = await compile(simplify(root), 'Dataset', { bannerComment: banner });

await writeFile(outFile, types);
console.log(`wrote ${outFile.pathname}`);
