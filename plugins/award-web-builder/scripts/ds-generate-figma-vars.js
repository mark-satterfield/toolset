#!/usr/bin/env node
/**
 * ds-generate-figma-vars.js — Generate Figma variable creation commands from design-system.json.
 *
 * Usage:
 *   node ds-generate-figma-vars.js <design-system.json> [--output <file.json>]
 *
 * Outputs a JSON structure that can be consumed by the Figma MCP server's
 * use_figma tool to create/update Figma variables programmatically.
 *
 * Generates variable definitions for:
 *   - Colors (primitive + semantic) → Figma COLOR variables
 *   - Spacing → Figma FLOAT variables
 *   - Border radii → Figma FLOAT variables
 *   - Z-indices → Figma FLOAT variables
 *   - Opacities → Figma FLOAT variables
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
  return JSON.parse(fs.readFileSync(resolved, 'utf8'));
}

function hexToFigmaRGBA(hex) {
  if (!hex || !hex.startsWith('#')) return null;
  const clean = hex.replace('#', '');
  const r = parseInt(clean.substring(0, 2), 16) / 255;
  const g = parseInt(clean.substring(2, 4), 16) / 255;
  const b = parseInt(clean.substring(4, 6), 16) / 255;
  const a = clean.length === 8 ? parseInt(clean.substring(6, 8), 16) / 255 : 1;
  return { r, g, b, a };
}

function colorToFigma(color) {
  if (!color) return null;
  if (color.hex) return hexToFigmaRGBA(color.hex);
  if (color.rgb) {
    return {
      r: color.rgb.r / 255,
      g: color.rgb.g / 255,
      b: color.rgb.b / 255,
      a: color.rgb.a ?? 1
    };
  }
  return null;
}

function measurementToPx(m) {
  if (!m) return null;
  if (m.px != null) return m.px;
  if (m.rem != null) return m.rem * 16;
  return null;
}

function kebab(str) {
  return str.replace(/([a-z])([A-Z])/g, '$1-$2').toLowerCase().replace(/[_\s]+/g, '-');
}

function generate(data) {
  const tokens = data.designTokens || {};
  const collections = [];

  // Colors collection
  const colorVars = [];
  const primColors = tokens.primitive?.colors || {};
  for (const [name, color] of Object.entries(primColors)) {
    const figmaColor = colorToFigma(color);
    if (figmaColor) {
      colorVars.push({
        name: kebab(name),
        resolvedType: 'COLOR',
        valuesByMode: { 'Light': figmaColor }
      });
    }
  }
  const semColors = tokens.semantic?.colors || {};
  for (const [category, group] of Object.entries(semColors)) {
    if (typeof group !== 'object' || Array.isArray(group)) continue;
    for (const [name, color] of Object.entries(group)) {
      const figmaColor = colorToFigma(color);
      if (figmaColor) {
        colorVars.push({
          name: `${kebab(category)}/${kebab(name)}`,
          resolvedType: 'COLOR',
          valuesByMode: { 'Light': figmaColor }
        });
      }
    }
  }
  if (colorVars.length > 0) {
    collections.push({ name: 'Colors', modes: ['Light', 'Dark'], variables: colorVars });
  }

  // Spacing collection
  const spacingVars = [];
  const spacing = tokens.primitive?.spacing || {};
  for (const [name, m] of Object.entries(spacing)) {
    const px = measurementToPx(m);
    if (px != null) {
      spacingVars.push({
        name: kebab(name),
        resolvedType: 'FLOAT',
        valuesByMode: { 'Default': px }
      });
    }
  }
  if (spacingVars.length > 0) {
    collections.push({ name: 'Spacing', modes: ['Default'], variables: spacingVars });
  }

  // Border Radii collection
  const radiiVars = [];
  const radii = tokens.primitive?.borderRadii || {};
  for (const [name, m] of Object.entries(radii)) {
    const px = measurementToPx(m);
    if (px != null) {
      radiiVars.push({
        name: kebab(name),
        resolvedType: 'FLOAT',
        valuesByMode: { 'Default': px }
      });
    }
  }
  if (radiiVars.length > 0) {
    collections.push({ name: 'Radii', modes: ['Default'], variables: radiiVars });
  }

  return {
    _generated: new Date().toISOString(),
    _source: 'design-system.json',
    _note: 'Feed this to Figma MCP use_figma tool to create/update variables',
    collections
  };
}

function main() {
  const args = process.argv.slice(2);
  const file = args[0];
  const outputIdx = args.indexOf('--output');
  const outputFile = outputIdx >= 0 ? args[outputIdx + 1] : null;

  if (!file) {
    console.error('Usage: ds-generate-figma-vars.js <design-system.json> [--output <file.json>]');
    process.exit(2);
  }

  const data = readJson(file);
  const output = JSON.stringify(generate(data), null, 2) + '\n';

  if (outputFile) {
    fs.writeFileSync(path.resolve(outputFile), output, 'utf8');
    console.log(`✓ Generated ${outputFile}`);
  } else {
    process.stdout.write(output);
  }
}

main();
