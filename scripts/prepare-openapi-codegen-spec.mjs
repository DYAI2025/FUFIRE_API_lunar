#!/usr/bin/env node
/**
 * Temporary OpenAPI 3.1 -> OpenAPI Generator 7.6.0 compatibility shim.
 *
 * The canonical contract remains spec/openapi/openapi.json. This script writes
 * spec/openapi/openapi.codegen.json for the TypeScript client generation job
 * only. It normalizes nullable parameter schemas and applies a tiny allow-list
 * of schema-item annotations needed by openapi-generator-cli v7.6.0. The
 * generator has incomplete OpenAPI 3.1 support and can crash in the
 * normalizer/inline-model resolver on these otherwise valid constructs.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { inspect } from 'node:util';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '..');
const inputPath = resolve(repoRoot, 'spec/openapi/openapi.json');
const outputPath = resolve(repoRoot, 'spec/openapi/openapi.codegen.json');
const HTTP_METHODS = new Set(['get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace']);

const spec = JSON.parse(readFileSync(inputPath, 'utf8'));
const codegenSpec = structuredClone(spec);
const normalized = [];
const compatibilityPatches = [];
const errors = [];

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function schemaExcerpt(schema) {
  const rendered = JSON.stringify(schema, null, 2);
  return (rendered ?? String(schema)).slice(0, 1000);
}

function recordChange(context, reason) {
  normalized.push({ ...context, reason });
}

function recordError(context, problem, schema) {
  errors.push({ ...context, problem, schema: schemaExcerpt(schema) });
}

function recordCompatibilityPatch(target, reason) {
  compatibilityPatches.push({ target, reason });
}

function describeContext(context) {
  if (context.location === 'components.parameters') {
    return `components.parameters.${context.parameterName}`;
  }
  if (context.location === 'components.schemas') {
    return `components.schemas.${context.parameterName}`;
  }
  return `${context.method.toUpperCase()} ${context.path} parameter ${context.parameterName}`;
}

function componentSchema(name) {
  const schema = codegenSpec.components?.schemas?.[name];
  if (!isPlainObject(schema)) {
    recordError(
      { location: 'components.schemas', parameterName: name },
      `expected components.schemas.${name} to exist for the CodeGen compatibility patch`,
      schema,
    );
  }
  return schema;
}

function normalizeTypeArray(schema, context) {
  if (!Array.isArray(schema.type)) {
    return schema;
  }

  const nonNullTypes = schema.type.filter((typeName) => typeName !== 'null');
  if (nonNullTypes.length !== 1) {
    recordError(
      context,
      `cannot safely reduce parameter schema type array ${inspect(schema.type)}`,
      schema,
    );
    return schema;
  }

  const nextSchema = { ...schema, type: nonNullTypes[0] };
  recordChange(context, `reduced type array ${JSON.stringify(schema.type)} -> ${JSON.stringify(nonNullTypes[0])}`);
  return nextSchema;
}

function normalizeAnyOf(schema, context) {
  if (!Array.isArray(schema.anyOf)) {
    return schema;
  }

  const originalLength = schema.anyOf.length;
  const branches = schema.anyOf.filter((branch) => {
    if (isPlainObject(branch) && Object.keys(branch).length === 0) {
      recordChange(context, 'removed empty anyOf branch');
      return false;
    }
    if (isPlainObject(branch) && branch.type === 'null') {
      recordChange(context, 'removed null anyOf branch');
      return false;
    }
    return true;
  });

  if (branches.length === 0) {
    recordError(context, 'anyOf normalization removed all branches', schema);
    return schema;
  }

  if (branches.length === 1) {
    const { anyOf: _discarded, ...siblings } = schema;
    recordChange(context, `simplified anyOf ${originalLength} -> 1 branch`);
    return { ...branches[0], ...siblings };
  }

  if (branches.length !== originalLength) {
    return { ...schema, anyOf: branches };
  }
  return schema;
}

function validateArraySchema(schema, context) {
  if (schema.type !== 'array') {
    return;
  }
  if (!isPlainObject(schema.items)) {
    recordError(context, 'array parameter schema is missing items', schema);
    return;
  }
  if (Array.isArray(schema.items.type)) {
    const nonNullItemTypes = schema.items.type.filter((typeName) => typeName !== 'null');
    if (nonNullItemTypes.length !== 1) {
      recordError(context, 'array parameter items.type is not unambiguous', schema);
    }
    return;
  }
  if (typeof schema.items.type !== 'string') {
    recordError(context, 'array parameter items.type is missing or not a string', schema);
  }
}

function normalizeSchema(schema, context) {
  if (!isPlainObject(schema)) {
    return schema;
  }

  let nextSchema = normalizeAnyOf(normalizeTypeArray(schema, context), context);

  if (Array.isArray(nextSchema.anyOf)) {
    nextSchema = {
      ...nextSchema,
      anyOf: nextSchema.anyOf.map((branch) => normalizeSchema(branch, context)),
    };
  }
  if (isPlainObject(nextSchema.items)) {
    nextSchema = {
      ...nextSchema,
      items: normalizeSchema(nextSchema.items, context),
    };
  }

  validateArraySchema(nextSchema, context);
  return nextSchema;
}

function normalizeParameter(parameter, context) {
  if (!isPlainObject(parameter.schema)) {
    return;
  }
  parameter.schema = normalizeSchema(parameter.schema, context);
}

function applyKnownComponentCompatibilityPatches() {
  // These two schemas are already effectively arrays in the canonical contract,
  // but their item schemas are underspecified for openapi-generator-cli v7.6.0.
  // Keep this allow-list tiny and fail loudly if the canonical shapes change.
  const wuxing = componentSchema('WuxingMappingResponse');
  const wuxingOrder = wuxing?.properties?.order;
  if (isPlainObject(wuxingOrder) && wuxingOrder.type === 'array' && isPlainObject(wuxingOrder.items) && Object.keys(wuxingOrder.items).length === 0) {
    wuxingOrder.items = { type: 'string' };
    recordCompatibilityPatch('components.schemas.WuxingMappingResponse.properties.order.items', 'set known Wu-Xing order item type to string');
  } else {
    recordError(
      { location: 'components.schemas', parameterName: 'WuxingMappingResponse.properties.order' },
      'unexpected Wu-Xing order schema; refusing to guess a CodeGen item type',
      wuxingOrder,
    );
  }

  const refDataManifest = componentSchema('RefDataManifest');
  const artifacts = refDataManifest?.properties?.artifacts;
  if (isPlainObject(artifacts) && artifacts.type === 'array' && artifacts.items === undefined) {
    artifacts.items = { type: 'object', additionalProperties: true };
    recordCompatibilityPatch('components.schemas.RefDataManifest.properties.artifacts.items', 'set refdata artifact item type to object');
  } else {
    recordError(
      { location: 'components.schemas', parameterName: 'RefDataManifest.properties.artifacts' },
      'unexpected refdata artifacts schema; refusing to guess a CodeGen item type',
      artifacts,
    );
  }
}

for (const [path, pathItem] of Object.entries(codegenSpec.paths ?? {})) {
  if (!isPlainObject(pathItem)) {
    continue;
  }
  for (const [method, operation] of Object.entries(pathItem)) {
    if (!HTTP_METHODS.has(method.toLowerCase()) || !isPlainObject(operation)) {
      continue;
    }
    for (const [index, parameter] of (operation.parameters ?? []).entries()) {
      if (!isPlainObject(parameter)) {
        continue;
      }
      normalizeParameter(parameter, {
        location: 'paths',
        path,
        method: method.toLowerCase(),
        parameterName: parameter.name ?? `#${index}`,
      });
    }
  }
}

for (const [parameterName, parameter] of Object.entries(codegenSpec.components?.parameters ?? {})) {
  if (!isPlainObject(parameter)) {
    continue;
  }
  normalizeParameter(parameter, {
    location: 'components.parameters',
    parameterName,
  });
}

applyKnownComponentCompatibilityPatches();

const uniqueChanges = new Map();
for (const entry of normalized) {
  const key = `${describeContext(entry)}: ${entry.reason}`;
  uniqueChanges.set(key, entry);
}

const affectedParameters = new Set([...uniqueChanges.values()].map((entry) => describeContext(entry)));
console.log(`OpenAPI CodeGen compatibility shim: normalized ${affectedParameters.size} parameter(s), ${uniqueChanges.size} parameter schema change(s).`);
for (const entry of uniqueChanges.values()) {
  console.log(`- ${describeContext(entry)}: ${entry.reason}`);
}
console.log(`OpenAPI CodeGen compatibility shim: applied ${compatibilityPatches.length} known component schema patch(es).`);
for (const patch of compatibilityPatches) {
  console.log(`- ${patch.target}: ${patch.reason}`);
}

if (errors.length > 0) {
  console.error(`OpenAPI CodeGen compatibility shim: ${errors.length} non-normalizable schema issue(s).`);
  for (const error of errors) {
    console.error(`\n${describeContext(error)}`);
    console.error(`Problem: ${error.problem}`);
    console.error(`Schema excerpt:\n${error.schema}`);
  }
  process.exit(1);
}

writeFileSync(outputPath, `${JSON.stringify(codegenSpec, null, 2)}\n`);
console.log(`Wrote ${outputPath}`);
