#!/usr/bin/env node
/**
 * glassify-svg.js
 *
 * Converts an SVG logo into a glass-material version by injecting
 * SVG filter definitions. No runtime dependencies beyond Node built-ins.
 *
 * Usage:
 *   node glassify-svg.js input.svg [output.svg] [--preset=standard] [--param=value ...]
 *
 * Presets: subtle, standard, frosted, crystal, colored
 *
 * Parameters (override any preset value):
 *   --blur=3  --tint=#ffffff  --tintOpacity=0.15  --highlightAngle=135
 *   --highlightOpacity=0.4  --specularX=0.3  --specularY=0.25
 *   --specularRadius=0.15   --specularOpacity=0.5  --innerShadow=4
 *   --innerShadowAlpha=0.3  --saturation=1.2  --edgeHighlight=0.5
 *   --card  (wrap in glass card)
 *   --cardPadding=0.2  (fraction of card for padding)
 */

const fs = require('fs')
const path = require('path')

// ── Presets ──────────────────────────────────────────────────────────────

const PRESETS = {
  subtle:   { blur: 2, tint: '#ffffff', tintOpacity: 0.08, highlightAngle: 135, highlightOpacity: 0.25, specularX: 0.3, specularY: 0.25, specularRadius: 0.15, specularOpacity: 0.3,  innerShadow: 3,  innerShadowAlpha: 0.2, saturation: 1.1, edgeHighlight: 0.3 },
  standard: { blur: 3, tint: '#ffffff', tintOpacity: 0.15, highlightAngle: 135, highlightOpacity: 0.4,  specularX: 0.3, specularY: 0.25, specularRadius: 0.15, specularOpacity: 0.5,  innerShadow: 4,  innerShadowAlpha: 0.3, saturation: 1.2, edgeHighlight: 0.5 },
  frosted:  { blur: 8, tint: '#ffffff', tintOpacity: 0.22, highlightAngle: 135, highlightOpacity: 0.3,  specularX: 0.3, specularY: 0.25, specularRadius: 0.15, specularOpacity: 0.35, innerShadow: 5,  innerShadowAlpha: 0.35, saturation: 1.15, edgeHighlight: 0.4 },
  crystal:  { blur: 1, tint: '#ffffff', tintOpacity: 0.05, highlightAngle: 135, highlightOpacity: 0.55, specularX: 0.3, specularY: 0.25, specularRadius: 0.12, specularOpacity: 0.7,  innerShadow: 2,  innerShadowAlpha: 0.15, saturation: 1.3, edgeHighlight: 0.6 },
  colored:  { blur: 4, tint: '#4a90d9', tintOpacity: 0.25, highlightAngle: 135, highlightOpacity: 0.35, specularX: 0.3, specularY: 0.25, specularRadius: 0.15, specularOpacity: 0.4,  innerShadow: 4,  innerShadowAlpha: 0.3, saturation: 1.4, edgeHighlight: 0.45 },
}

// ── Argument Parsing ─────────────────────────────────────────────────────

function parseArgs(argv) {
  const args = argv.slice(2)
  const positional = []
  const flags = {}

  for (const arg of args) {
    if (arg.startsWith('--')) {
      const [key, val] = arg.slice(2).split('=')
      flags[key] = val === undefined ? true : val
    } else {
      positional.push(arg)
    }
  }

  const inputFile = positional[0]
  if (!inputFile) {
    console.error('Usage: glassify-svg.js input.svg [output.svg] [--preset=standard] [--param=value ...]')
    process.exit(1)
  }

  const presetName = flags.preset || 'standard'
  const preset = PRESETS[presetName]
  if (!preset) {
    console.error(`Unknown preset: ${presetName}. Available: ${Object.keys(PRESETS).join(', ')}`)
    process.exit(1)
  }

  // Override preset with explicit flags
  const params = { ...preset }
  for (const [key, val] of Object.entries(flags)) {
    if (key === 'preset' || key === 'card' || key === 'cardPadding') continue
    if (key in params) {
      params[key] = typeof params[key] === 'number' ? parseFloat(val) : val
    }
  }

  const ext = path.extname(inputFile)
  const base = path.basename(inputFile, ext)
  const suffix = flags.card ? '-glass-card' : '-glass'
  const outputFile = positional[1] || path.join(path.dirname(inputFile), `${base}${suffix}.svg`)

  return {
    inputFile,
    outputFile,
    params,
    wrapCard: !!flags.card,
    cardPadding: parseFloat(flags.cardPadding || '0.2'),
  }
}

// ── SVG Dimension Extraction ─────────────────────────────────────────────

function extractDimensions(svgContent) {
  const widthMatch = svgContent.match(/\bwidth\s*=\s*["']([^"']+)["']/)
  const heightMatch = svgContent.match(/\bheight\s*=\s*["']([^"']+)["']/)
  const viewBoxMatch = svgContent.match(/\bviewBox\s*=\s*["']([^"']+)["']/)

  let width = 100, height = 100

  if (viewBoxMatch) {
    const parts = viewBoxMatch[1].trim().split(/[\s,]+/)
    width = parseFloat(parts[2])
    height = parseFloat(parts[3])
  }
  if (widthMatch) width = parseFloat(widthMatch[1])
  if (heightMatch) height = parseFloat(heightMatch[1])

  return { width, height, viewBox: viewBoxMatch ? viewBoxMatch[1] : `0 0 ${width} ${height}` }
}

// ── Filter Generation ────────────────────────────────────────────────────

function buildGlassFilter(params, width, height) {
  const { blur, tint, tintOpacity, highlightAngle, highlightOpacity,
          specularX, specularY, specularOpacity,
          innerShadow, innerShadowAlpha, saturation, edgeHighlight } = params

  const rad = (highlightAngle * Math.PI) / 180
  const gx2 = Math.round(50 + 50 * Math.cos(rad))
  const gy2 = Math.round(50 + 50 * Math.sin(rad))
  const lightX = Math.round(specularX * width)
  const lightY = Math.round(specularY * height)

  return `
  <defs>
    <filter id="glassify" x="-10%" y="-10%" width="120%" height="120%"
            color-interpolation-filters="sRGB">

      <!-- Tint fill clipped to shape -->
      <feFlood flood-color="${tint}" flood-opacity="${tintOpacity}" result="tint"/>
      <feComposite in="tint" in2="SourceAlpha" operator="in" result="tintedFill"/>

      <!-- Inner frosting -->
      <feGaussianBlur in="SourceAlpha" stdDeviation="${blur}" result="innerBlur"/>
      <feComposite in="innerBlur" in2="SourceAlpha" operator="in" result="frost"/>

      <!-- Inner shadow -->
      <feOffset in="SourceAlpha" dx="2" dy="2" result="shadowOffset"/>
      <feGaussianBlur in="shadowOffset" stdDeviation="${innerShadow}" result="shadowBlur"/>
      <feFlood flood-color="#000000" flood-opacity="${innerShadowAlpha}" result="shadowColor"/>
      <feComposite in="shadowColor" in2="shadowBlur" operator="in" result="innerShadow"/>
      <feComposite in="innerShadow" in2="SourceAlpha" operator="in" result="clippedShadow"/>

      <!-- Specular lighting -->
      <feSpecularLighting in="frost" surfaceScale="5" specularConstant="0.8"
                          specularExponent="20" lighting-color="#ffffff" result="specRaw">
        <fePointLight x="${lightX}" y="${lightY}" z="200"/>
      </feSpecularLighting>
      <feComposite in="specRaw" in2="SourceAlpha" operator="in" result="specular"/>

      <!-- Saturation -->
      <feColorMatrix in="SourceGraphic" type="saturate" values="${saturation}"
                     result="saturated"/>
      <feComposite in="saturated" in2="SourceAlpha" operator="in" result="saturatedClipped"/>

      <!-- Merge layers -->
      <feMerge>
        <feMergeNode in="saturatedClipped"/>
        <feMergeNode in="tintedFill"/>
        <feMergeNode in="frost"/>
        <feMergeNode in="clippedShadow"/>
        <feMergeNode in="specular"/>
      </feMerge>
    </filter>

    <!-- Edge highlight gradient -->
    <linearGradient id="glassify-edge" x1="0%" y1="0%"
                    x2="${gx2}%" y2="${gy2}%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="${edgeHighlight}"/>
      <stop offset="50%" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="${(edgeHighlight * 0.3).toFixed(2)}"/>
    </linearGradient>
  </defs>`
}

// ── Glass Card Wrapper ───────────────────────────────────────────────────

function wrapInCard(innerSvg, innerWidth, innerHeight, padding) {
  const padX = Math.round(innerWidth * padding)
  const padY = Math.round(innerHeight * padding)
  const cardW = innerWidth + padX * 2
  const cardH = innerHeight + padY * 2
  const radius = 20

  return `<svg xmlns="http://www.w3.org/2000/svg"
     width="${cardW}" height="${cardH}"
     viewBox="0 0 ${cardW} ${cardH}">
  <defs>
    <clipPath id="card-clip">
      <rect width="${cardW}" height="${cardH}" rx="${radius}" ry="${radius}"/>
    </clipPath>
  </defs>

  <!-- Card background -->
  <g clip-path="url(#card-clip)">
    <rect width="${cardW}" height="${cardH}" fill="rgba(255,255,255,0.15)"/>
    <rect width="${cardW}" height="${cardH}" fill="rgba(255,255,255,0.08)"/>

    <!-- Top edge highlight -->
    <line x1="${cardW * 0.1}" y1="0.5" x2="${cardW * 0.9}" y2="0.5"
          stroke="rgba(255,255,255,0.4)" stroke-width="1"/>

    <!-- Inner highlight gradient -->
    <rect width="${cardW}" height="${cardH * 0.5}"
          fill="rgba(255,255,255,0.06)"/>
  </g>

  <!-- Card border -->
  <rect width="${cardW}" height="${cardH}" rx="${radius}" ry="${radius}"
        fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="1"/>

  <!-- Card shadow -->
  <rect width="${cardW}" height="${cardH}" rx="${radius}" ry="${radius}"
        fill="none" style="filter: drop-shadow(0 8px 32px rgba(31,38,135,0.2));"/>

  <!-- Logo centered -->
  <g transform="translate(${padX}, ${padY})">
    ${innerSvg}
  </g>
</svg>`
}

// ── Main Transform ───────────────────────────────────────────────────────

function glassifySvg(svgContent, params) {
  const { width, height, viewBox } = extractDimensions(svgContent)
  const filterDefs = buildGlassFilter(params, width, height)

  // Remove existing <defs> closing and inject ours, or add before closing </svg>
  let result = svgContent

  // Check if <defs> exists
  if (/<defs[\s>]/i.test(result)) {
    // Inject our filter inside existing <defs>
    result = result.replace(/<\/defs>/i, `${filterDefs.replace(/<\/?defs>/g, '')}\n  </defs>`)
  } else {
    // Insert <defs> block after opening <svg> tag
    result = result.replace(/(<svg[^>]*>)/i, `$1\n${filterDefs}`)
  }

  // Wrap all non-defs content in a filtered group
  // Strategy: find closing </svg>, insert group wrapper before it
  const closingSvg = '</svg>'
  const closingIdx = result.lastIndexOf(closingSvg)
  if (closingIdx === -1) {
    throw new Error('Malformed SVG: no closing </svg> tag')
  }

  // Extract everything between <defs>...</defs> and the shapes
  // Simpler approach: wrap content between last </defs> and </svg>
  const defsEnd = result.lastIndexOf('</defs>')
  const contentStart = defsEnd !== -1 ? defsEnd + '</defs>'.length : result.indexOf('>') + 1
  const content = result.slice(contentStart, closingIdx)

  const filtered = `
  <g filter="url(#glassify)" stroke="url(#glassify-edge)" stroke-width="0.5">
    ${content}
  </g>`

  result = result.slice(0, contentStart) + filtered + '\n' + closingSvg

  return { result, width, height }
}

// ── Entry Point ──────────────────────────────────────────────────────────

function main() {
  const { inputFile, outputFile, params, wrapCard, cardPadding } = parseArgs(process.argv)

  if (!fs.existsSync(inputFile)) {
    console.error(`File not found: ${inputFile}`)
    process.exit(1)
  }

  const svgContent = fs.readFileSync(inputFile, 'utf-8')

  if (!/<svg[\s>]/i.test(svgContent)) {
    console.error('Input does not appear to be an SVG file')
    process.exit(1)
  }

  let { result, width, height } = glassifySvg(svgContent, params)

  if (wrapCard) {
    result = wrapInCard(result, width, height, cardPadding)
  }

  fs.writeFileSync(outputFile, result, 'utf-8')
  console.log(`Output: ${outputFile}`)
  console.log(`Params: ${JSON.stringify(params, null, 2)}`)
}

main()
