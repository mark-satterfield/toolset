#!/usr/bin/env node
/**
 * ds-generate-css.js — Generate CSS custom properties from design-system.json.
 *
 * Usage:
 *   node ds-generate-css.js <design-system.json> [--output <file.css>] [--theme <themeId>]
 *
 * Generates :root CSS custom properties from:
 *   - designTokens.primitive.colors → --primitive-{name}
 *   - designTokens.semantic.colors → --{category}-{name}
 *   - designTokens.primitive.spacing → --space-{name}
 *   - designTokens.primitive.borderRadii → --radius-{name}
 *   - designTokens.primitive.zIndices → --z-{name}
 *   - designTokens.primitive.opacities → --opacity-{name}
 *   - designTokens.motion.durations → --duration-{name}
 *   - designTokens.elevation.levels → --shadow-{label}
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

function colorToCSS(color) {
  if (!color) return null;
  if (color.hex) return color.hex;
  if (color.rgb) {
    const { r, g, b, a } = color.rgb;
    return a != null && a < 1
      ? `rgba(${r}, ${g}, ${b}, ${a})`
      : `rgb(${r}, ${g}, ${b})`;
  }
  if (color.hsl) {
    const { h, s, l, a } = color.hsl;
    return a != null && a < 1
      ? `hsla(${h}, ${s}%, ${l}%, ${a})`
      : `hsl(${h}, ${s}%, ${l}%)`;
  }
  return null;
}

function measurementToCSS(m) {
  if (!m) return null;
  if (m.px != null) return `${m.px}px`;
  if (m.rem != null) return `${m.rem}rem`;
  if (m.em != null) return `${m.em}em`;
  if (m.percent != null) return `${m.percent}%`;
  return null;
}

function shadowToCSS(s) {
  if (!s) return null;
  const x = measurementToCSS(s.offsetX) || '0';
  const y = measurementToCSS(s.offsetY) || '0';
  const blur = measurementToCSS(s.blurRadius) || '0';
  const spread = measurementToCSS(s.spreadRadius) || '0';
  const color = colorToCSS(s.color) || 'rgba(0,0,0,0.1)';
  const inset = s.inset ? 'inset ' : '';
  return `${inset}${x} ${y} ${blur} ${spread} ${color}`;
}

function kebab(str) {
  return str.replace(/([a-z])([A-Z])/g, '$1-$2').toLowerCase().replace(/[_\s]+/g, '-');
}

function generate(data) {
  const lines = [];
  const tokens = data.designTokens || {};

  lines.push('/* Auto-generated from design-system.json — do not edit manually */');
  lines.push(':root {');

  // Primitive colors
  const primColors = tokens.primitive?.colors || {};
  for (const [name, color] of Object.entries(primColors)) {
    const css = colorToCSS(color);
    if (css) lines.push(`  --${kebab(name)}: ${css};`);
  }

  // Semantic colors
  const semColors = tokens.semantic?.colors || {};
  for (const [category, group] of Object.entries(semColors)) {
    if (typeof group !== 'object' || Array.isArray(group)) continue;
    for (const [name, color] of Object.entries(group)) {
      const css = colorToCSS(color);
      if (css) lines.push(`  --${kebab(category)}-${kebab(name)}: ${css};`);
    }
  }

  // Spacing
  const spacing = tokens.primitive?.spacing || {};
  for (const [name, m] of Object.entries(spacing)) {
    const css = measurementToCSS(m);
    if (css) lines.push(`  --space-${kebab(name)}: ${css};`);
  }

  // Semantic spacing
  const semSpacing = tokens.semantic?.spacing || {};
  for (const [name, m] of Object.entries(semSpacing)) {
    const css = measurementToCSS(m);
    if (css) lines.push(`  --spacing-${kebab(name)}: ${css};`);
  }

  // Border radii
  const radii = tokens.primitive?.borderRadii || {};
  for (const [name, m] of Object.entries(radii)) {
    const css = measurementToCSS(m);
    if (css) lines.push(`  --radius-${kebab(name)}: ${css};`);
  }

  // Z-indices
  const zIndices = tokens.primitive?.zIndices || {};
  for (const [name, val] of Object.entries(zIndices)) {
    lines.push(`  --z-${kebab(name)}: ${val};`);
  }

  // Opacities
  const opacities = tokens.primitive?.opacities || {};
  for (const [name, val] of Object.entries(opacities)) {
    lines.push(`  --opacity-${kebab(name)}: ${val};`);
  }

  // Durations
  const durations = tokens.motion?.durations || {};
  for (const [name, val] of Object.entries(durations)) {
    lines.push(`  --duration-${kebab(name)}: ${val}ms;`);
  }

  // Elevation shadows
  const levels = tokens.elevation?.levels || [];
  for (const level of levels) {
    if (level.label && level.shadows) {
      const shadowCSS = level.shadows.map(shadowToCSS).filter(Boolean).join(', ');
      if (shadowCSS) lines.push(`  --shadow-${kebab(level.label)}: ${shadowCSS};`);
    }
    if (level.label && level.zIndex != null) {
      lines.push(`  --z-${kebab(level.label)}: ${level.zIndex};`);
    }
  }

  lines.push('}');

  // Reduced motion
  lines.push('');
  lines.push('@media (prefers-reduced-motion: reduce) {');
  lines.push('  :root {');
  for (const [name] of Object.entries(durations)) {
    lines.push(`    --duration-${kebab(name)}: 0ms;`);
  }
  lines.push('  }');
  lines.push('}');

  return lines.join('\n') + '\n';
}

function main() {
  const args = process.argv.slice(2);
  const file = args[0];
  const outputIdx = args.indexOf('--output');
  const outputFile = outputIdx >= 0 ? args[outputIdx + 1] : null;

  if (!file) {
    console.error('Usage: ds-generate-css.js <design-system.json> [--output <file.css>]');
    process.exit(2);
  }

  const data = readJson(file);
  const css = generate(data);

  if (outputFile) {
    fs.writeFileSync(path.resolve(outputFile), css, 'utf8');
    console.log(`✓ Generated ${outputFile}`);
  } else {
    process.stdout.write(css);
  }
}

main();
