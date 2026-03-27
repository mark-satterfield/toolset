#!/usr/bin/env node
/**
 * ds-validate.js — Validate a design-system.json against the schema.
 *
 * Usage:
 *   node ds-validate.js <design-system.json>
 *   node ds-validate.js design-system/skillspoke.json
 *
 * Exit codes:
 *   0 = valid
 *   1 = validation errors found
 *   2 = file not found or parse error
 *
 * Dependencies: ajv (declared in package.json)
 */
'use strict';

const fs = require('fs');
const path = require('path');

// Lazy-load Ajv to give a clear error if not installed
let Ajv;
try {
  Ajv = require('ajv');
} catch {
  console.error('Missing dependency: ajv — see package.json for required dependencies');
  process.exit(2);
}

const SCHEMA_PATH = path.join(__dirname, '..', 'references', 'design-system.schema.json');

function main() {
  const targetPath = process.argv[2];
  if (!targetPath) {
    console.error('Usage: node ds-validate.js <design-system.json>');
    process.exit(2);
  }

  const resolvedTarget = path.resolve(targetPath);
  if (!fs.existsSync(resolvedTarget)) {
    console.error(`File not found: ${resolvedTarget}`);
    process.exit(2);
  }
  if (!fs.existsSync(SCHEMA_PATH)) {
    console.error(`Schema not found: ${SCHEMA_PATH}`);
    process.exit(2);
  }

  let schema, data;
  try {
    schema = JSON.parse(fs.readFileSync(SCHEMA_PATH, 'utf8'));
  } catch (e) {
    console.error(`Schema parse error: ${e.message}`);
    process.exit(2);
  }
  try {
    data = JSON.parse(fs.readFileSync(resolvedTarget, 'utf8'));
  } catch (e) {
    console.error(`JSON parse error in ${resolvedTarget}: ${e.message}`);
    process.exit(2);
  }

  const ajv = new Ajv({ allErrors: true, verbose: true });
  const validate = ajv.compile(schema);
  const valid = validate(data);

  if (valid) {
    console.log(`✓ Valid — ${resolvedTarget} conforms to design-system schema`);
    process.exit(0);
  } else {
    console.error(`✗ Validation failed — ${validate.errors.length} error(s):\n`);
    for (const err of validate.errors) {
      const loc = err.instancePath || '(root)';
      console.error(`  ${loc}: ${err.message}`);
      if (err.params) {
        const details = Object.entries(err.params)
          .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
          .join(', ');
        console.error(`    (${details})`);
      }
    }
    process.exit(1);
  }
}

main();
