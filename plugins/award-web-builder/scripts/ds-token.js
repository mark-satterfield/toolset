#!/usr/bin/env node
/**
 * ds-token.js — CRUD operations on design-system.json tokens.
 *
 * Usage:
 *   node ds-token.js get <file> <dot.path>
 *   node ds-token.js set <file> <dot.path> <value>
 *   node ds-token.js delete <file> <dot.path>
 *   node ds-token.js list <file> [prefix]
 *   node ds-token.js search <file> <query>
 *   node ds-token.js diff <file1> <file2>
 *
 * Examples:
 *   node ds-token.js get ds.json designTokens.primitive.colors.steelNavy.hex
 *   node ds-token.js set ds.json designTokens.primitive.colors.steelNavy.hex "#1a3550"
 *   node ds-token.js list ds.json designTokens.semantic.colors
 *   node ds-token.js search ds.json "amber"
 *   node ds-token.js diff ds-v1.json ds-v2.json
 *
 * No dependencies — stdlib only.
 */
'use strict';

const fs = require('fs');
const path = require('path');

function readJson(filePath) {
  const resolved = path.resolve(filePath);
  if (!fs.existsSync(resolved)) {
    console.error(`File not found: ${resolved}`);
    process.exit(2);
  }
  try {
    return JSON.parse(fs.readFileSync(resolved, 'utf8'));
  } catch (e) {
    console.error(`Parse error: ${e.message}`);
    process.exit(2);
  }
}

function writeJson(filePath, data) {
  fs.writeFileSync(path.resolve(filePath), JSON.stringify(data, null, 2) + '\n', 'utf8');
}

function getByPath(obj, dotPath) {
  const keys = dotPath.split('.');
  let current = obj;
  for (const key of keys) {
    if (current == null || typeof current !== 'object') return undefined;
    current = current[key];
  }
  return current;
}

function setByPath(obj, dotPath, value) {
  const keys = dotPath.split('.');
  let current = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    if (current[keys[i]] == null || typeof current[keys[i]] !== 'object') {
      current[keys[i]] = {};
    }
    current = current[keys[i]];
  }
  // Try to parse value as JSON, fall back to string
  try {
    current[keys[keys.length - 1]] = JSON.parse(value);
  } catch {
    current[keys[keys.length - 1]] = value;
  }
}

function deleteByPath(obj, dotPath) {
  const keys = dotPath.split('.');
  let current = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    if (current[keys[i]] == null) return false;
    current = current[keys[i]];
  }
  if (current.hasOwnProperty(keys[keys.length - 1])) {
    delete current[keys[keys.length - 1]];
    return true;
  }
  return false;
}

function collectPaths(obj, prefix = '') {
  const paths = [];
  if (obj == null || typeof obj !== 'object') {
    paths.push({ path: prefix, value: obj });
    return paths;
  }
  if (Array.isArray(obj)) {
    paths.push({ path: prefix, value: `[Array(${obj.length})]` });
    return paths;
  }
  for (const [key, val] of Object.entries(obj)) {
    const fullPath = prefix ? `${prefix}.${key}` : key;
    if (val != null && typeof val === 'object' && !Array.isArray(val)) {
      paths.push(...collectPaths(val, fullPath));
    } else {
      paths.push({ path: fullPath, value: val });
    }
  }
  return paths;
}

function diffObjects(obj1, obj2, prefix = '') {
  const diffs = [];
  const allKeys = new Set([
    ...Object.keys(obj1 || {}),
    ...Object.keys(obj2 || {})
  ]);

  for (const key of allKeys) {
    const fullPath = prefix ? `${prefix}.${key}` : key;
    const v1 = obj1?.[key];
    const v2 = obj2?.[key];

    if (v1 === undefined && v2 !== undefined) {
      diffs.push({ path: fullPath, type: 'added', value: v2 });
    } else if (v1 !== undefined && v2 === undefined) {
      diffs.push({ path: fullPath, type: 'removed', value: v1 });
    } else if (typeof v1 === 'object' && typeof v2 === 'object' && v1 !== null && v2 !== null && !Array.isArray(v1) && !Array.isArray(v2)) {
      diffs.push(...diffObjects(v1, v2, fullPath));
    } else if (JSON.stringify(v1) !== JSON.stringify(v2)) {
      diffs.push({ path: fullPath, type: 'changed', from: v1, to: v2 });
    }
  }
  return diffs;
}

function main() {
  const [, , command, ...args] = process.argv;

  switch (command) {
    case 'get': {
      const [file, dotPath] = args;
      if (!file || !dotPath) { console.error('Usage: ds-token.js get <file> <dot.path>'); process.exit(2); }
      const data = readJson(file);
      const result = getByPath(data, dotPath);
      if (result === undefined) {
        console.error(`Not found: ${dotPath}`);
        process.exit(1);
      }
      console.log(typeof result === 'object' ? JSON.stringify(result, null, 2) : result);
      break;
    }

    case 'set': {
      const [file, dotPath, ...valueParts] = args;
      const value = valueParts.join(' ');
      if (!file || !dotPath || !value) { console.error('Usage: ds-token.js set <file> <dot.path> <value>'); process.exit(2); }
      const data = readJson(file);
      setByPath(data, dotPath, value);
      writeJson(file, data);
      console.log(`✓ Set ${dotPath}`);
      break;
    }

    case 'delete': {
      const [file, dotPath] = args;
      if (!file || !dotPath) { console.error('Usage: ds-token.js delete <file> <dot.path>'); process.exit(2); }
      const data = readJson(file);
      if (deleteByPath(data, dotPath)) {
        writeJson(file, data);
        console.log(`✓ Deleted ${dotPath}`);
      } else {
        console.error(`Not found: ${dotPath}`);
        process.exit(1);
      }
      break;
    }

    case 'list': {
      const [file, prefix] = args;
      if (!file) { console.error('Usage: ds-token.js list <file> [prefix]'); process.exit(2); }
      const data = readJson(file);
      const target = prefix ? getByPath(data, prefix) : data;
      if (target === undefined) { console.error(`Not found: ${prefix}`); process.exit(1); }
      const paths = collectPaths(target, prefix || '');
      for (const { path: p, value } of paths) {
        const display = Array.isArray(value) ? `[Array(${value.length})]` : typeof value === 'object' ? '{...}' : JSON.stringify(value);
        console.log(`${p} = ${display}`);
      }
      break;
    }

    case 'search': {
      const [file, query] = args;
      if (!file || !query) { console.error('Usage: ds-token.js search <file> <query>'); process.exit(2); }
      const data = readJson(file);
      const paths = collectPaths(data);
      const lowerQuery = query.toLowerCase();
      const matches = paths.filter(({ path: p, value }) =>
        p.toLowerCase().includes(lowerQuery) ||
        String(value).toLowerCase().includes(lowerQuery)
      );
      if (matches.length === 0) {
        console.log(`No matches for "${query}"`);
      } else {
        for (const { path: p, value } of matches) {
          console.log(`${p} = ${JSON.stringify(value)}`);
        }
      }
      break;
    }

    case 'diff': {
      const [file1, file2] = args;
      if (!file1 || !file2) { console.error('Usage: ds-token.js diff <file1> <file2>'); process.exit(2); }
      const data1 = readJson(file1);
      const data2 = readJson(file2);
      const diffs = diffObjects(data1, data2);
      if (diffs.length === 0) {
        console.log('No differences');
      } else {
        console.log(`${diffs.length} difference(s):\n`);
        for (const d of diffs) {
          if (d.type === 'added') console.log(`  + ${d.path} = ${JSON.stringify(d.value)}`);
          else if (d.type === 'removed') console.log(`  - ${d.path} = ${JSON.stringify(d.value)}`);
          else console.log(`  ~ ${d.path}: ${JSON.stringify(d.from)} → ${JSON.stringify(d.to)}`);
        }
      }
      break;
    }

    default:
      console.error('Commands: get, set, delete, list, search, diff');
      process.exit(2);
  }
}

main();
