#!/usr/bin/env node
/**
 * glassify-png.js
 *
 * Converts a PNG logo with transparency into a glass-material version
 * using Canvas API compositing.
 *
 * Dependencies:
 *   npm install canvas
 *
 * Usage:
 *   node glassify-png.js input.png [output.png] [--preset=standard] [--param=value ...]
 *
 * Presets: subtle, standard, frosted, crystal, colored
 *
 * Parameters (override any preset value):
 *   --blur=3  --tint=#ffffff  --tintOpacity=0.15  --highlightAngle=135
 *   --highlightOpacity=0.4  --specularX=0.3  --specularY=0.25
 *   --specularRadius=0.15   --specularOpacity=0.5  --innerShadow=4
 *   --innerShadowAlpha=0.3  --saturation=1.2  --edgeHighlight=0.5
 *   --card  (wrap in glass card)
 *   --cardPadding=0.2
 */

const fs = require('fs')
const path = require('path')
const { createCanvas, loadImage } = require('canvas')

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
    console.error('Usage: glassify-png.js input.png [output.png] [--preset=standard] [--param=value ...]')
    process.exit(1)
  }

  const presetName = flags.preset || 'standard'
  const preset = PRESETS[presetName]
  if (!preset) {
    console.error(`Unknown preset: ${presetName}. Available: ${Object.keys(PRESETS).join(', ')}`)
    process.exit(1)
  }

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
  const outputFile = positional[1] || path.join(path.dirname(inputFile), `${base}${suffix}.png`)

  return {
    inputFile,
    outputFile,
    params,
    wrapCard: !!flags.card,
    cardPadding: parseFloat(flags.cardPadding || '0.2'),
  }
}

// ── Hex to RGBA ──────────────────────────────────────────────────────────

function hexToRgba(hex, alpha) {
  const h = hex.replace('#', '')
  const r = parseInt(h.substring(0, 2), 16)
  const g = parseInt(h.substring(2, 4), 16)
  const b = parseInt(h.substring(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

// ── Alpha Check ──────────────────────────────────────────────────────────

function hasTransparency(ctx, width, height) {
  const data = ctx.getImageData(0, 0, width, height).data
  for (let i = 3; i < data.length; i += 4) {
    if (data[i] < 255) return true
  }
  return false
}

// ── Create Alpha Mask Canvas ─────────────────────────────────────────────

function createAlphaMask(sourceCtx, width, height) {
  const mask = createCanvas(width, height)
  const mCtx = mask.getContext('2d')
  const srcData = sourceCtx.getImageData(0, 0, width, height)
  const maskData = mCtx.createImageData(width, height)

  for (let i = 0; i < srcData.data.length; i += 4) {
    const a = srcData.data[i + 3]
    maskData.data[i] = 255     // R
    maskData.data[i + 1] = 255 // G
    maskData.data[i + 2] = 255 // B
    maskData.data[i + 3] = a   // A (preserve original alpha)
  }

  mCtx.putImageData(maskData, 0, 0)
  return mask
}

// ── Clip to Alpha ────────────────────────────────────────────────────────

function clipToAlpha(layerCanvas, alphaMask) {
  const ctx = layerCanvas.getContext('2d')
  ctx.globalCompositeOperation = 'destination-in'
  ctx.drawImage(alphaMask, 0, 0)
  ctx.globalCompositeOperation = 'source-over'
}

// ── Main Glassify ────────────────────────────────────────────────────────

async function glassifyPng(inputFile, params) {
  const img = await loadImage(inputFile)
  const { width, height } = img

  // Source canvas
  const srcCanvas = createCanvas(width, height)
  const srcCtx = srcCanvas.getContext('2d')
  srcCtx.drawImage(img, 0, 0)

  if (!hasTransparency(srcCtx, width, height)) {
    console.error('ERROR: Input PNG has no transparency. Glassify requires an alpha channel.')
    console.error('Provide a PNG with a transparent background.')
    process.exit(1)
  }

  const alphaMask = createAlphaMask(srcCtx, width, height)

  // Output canvas
  const out = createCanvas(width, height)
  const ctx = out.getContext('2d')

  // ── Layer 1: Saturated base ──

  const satLayer = createCanvas(width, height)
  const satCtx = satLayer.getContext('2d')
  // node-canvas supports ctx.filter in newer versions
  try {
    satCtx.filter = `saturate(${params.saturation * 100}%)`
  } catch {
    // fallback: draw without saturation filter
  }
  satCtx.drawImage(img, 0, 0)
  satCtx.filter = 'none'
  clipToAlpha(satLayer, alphaMask)
  ctx.drawImage(satLayer, 0, 0)

  // ── Layer 2: Glass tint fill ──

  const tintLayer = createCanvas(width, height)
  const tintCtx = tintLayer.getContext('2d')
  tintCtx.fillStyle = hexToRgba(params.tint, params.tintOpacity)
  tintCtx.fillRect(0, 0, width, height)
  clipToAlpha(tintLayer, alphaMask)
  ctx.drawImage(tintLayer, 0, 0)

  // ── Layer 3: Inner frosting ──

  if (params.blur > 0) {
    const frostLayer = createCanvas(width, height)
    const frostCtx = frostLayer.getContext('2d')
    try {
      frostCtx.filter = `blur(${params.blur}px)`
    } catch {
      // skip frosting if filter unsupported
    }
    frostCtx.drawImage(img, 0, 0)
    frostCtx.filter = 'none'
    clipToAlpha(frostLayer, alphaMask)
    ctx.globalAlpha = 0.3
    ctx.drawImage(frostLayer, 0, 0)
    ctx.globalAlpha = 1.0
  }

  // ── Layer 4: Inner shadow ──

  const shadowLayer = createCanvas(width, height)
  const shadowCtx = shadowLayer.getContext('2d')
  shadowCtx.shadowColor = `rgba(0,0,0,${params.innerShadowAlpha})`
  shadowCtx.shadowBlur = params.innerShadow
  shadowCtx.shadowOffsetX = 2
  shadowCtx.shadowOffsetY = 2
  shadowCtx.drawImage(alphaMask, 0, 0)
  // Clip shadow to original alpha
  shadowCtx.globalCompositeOperation = 'destination-in'
  shadowCtx.drawImage(alphaMask, 0, 0)
  shadowCtx.globalCompositeOperation = 'source-over'
  // Remove the white fill, keep only the shadow
  shadowCtx.globalCompositeOperation = 'destination-out'
  shadowCtx.drawImage(alphaMask, 0, 0)
  shadowCtx.globalCompositeOperation = 'source-over'
  ctx.drawImage(shadowLayer, 0, 0)

  // ── Layer 5: Gradient highlight ──

  const hlLayer = createCanvas(width, height)
  const hlCtx = hlLayer.getContext('2d')
  const rad = (params.highlightAngle * Math.PI) / 180
  const gx = width * 0.5 + width * 0.5 * Math.cos(rad)
  const gy = height * 0.5 + height * 0.5 * Math.sin(rad)
  const grad = hlCtx.createLinearGradient(0, 0, gx, gy)
  grad.addColorStop(0, `rgba(255,255,255,${params.highlightOpacity})`)
  grad.addColorStop(0.6, 'rgba(255,255,255,0)')
  hlCtx.fillStyle = grad
  hlCtx.fillRect(0, 0, width, height)
  clipToAlpha(hlLayer, alphaMask)
  ctx.drawImage(hlLayer, 0, 0)

  // ── Layer 6: Specular dot ──

  const specLayer = createCanvas(width, height)
  const specCtx = specLayer.getContext('2d')
  const sx = params.specularX * width
  const sy = params.specularY * height
  const sr = params.specularRadius * Math.min(width, height)
  const specGrad = specCtx.createRadialGradient(sx, sy, 0, sx, sy, sr)
  specGrad.addColorStop(0, `rgba(255,255,255,${params.specularOpacity})`)
  specGrad.addColorStop(1, 'rgba(255,255,255,0)')
  specCtx.fillStyle = specGrad
  specCtx.fillRect(0, 0, width, height)
  clipToAlpha(specLayer, alphaMask)
  ctx.drawImage(specLayer, 0, 0)

  // ── Layer 7: Edge highlight ──

  if (params.edgeHighlight > 0) {
    const edgeLayer = createCanvas(width, height)
    const edgeCtx = edgeLayer.getContext('2d')
    // Draw alpha mask shape as a stroked outline
    edgeCtx.drawImage(alphaMask, 0, 0)
    edgeCtx.globalCompositeOperation = 'source-in'
    edgeCtx.strokeStyle = `rgba(255,255,255,${params.edgeHighlight})`
    edgeCtx.lineWidth = 1.5
    // Use the mask itself — stroke by eroding and diffing
    edgeCtx.globalCompositeOperation = 'source-over'

    // Simpler approach: draw white outline via shadow trick
    const edgeLayer2 = createCanvas(width, height)
    const edgeCtx2 = edgeLayer2.getContext('2d')
    edgeCtx2.shadowColor = `rgba(255,255,255,${params.edgeHighlight})`
    edgeCtx2.shadowBlur = 1
    edgeCtx2.drawImage(alphaMask, 0, 0)
    // Subtract the interior to leave only the edge glow
    edgeCtx2.globalCompositeOperation = 'destination-out'
    edgeCtx2.drawImage(alphaMask, 0, 0)
    edgeCtx2.globalCompositeOperation = 'source-over'
    ctx.drawImage(edgeLayer2, 0, 0)
  }

  return { canvas: out, width, height }
}

// ── Glass Card ───────────────────────────────────────────────────────────

function wrapInCard(logoCanvas, logoWidth, logoHeight, padding) {
  const padX = Math.round(logoWidth * padding)
  const padY = Math.round(logoHeight * padding)
  const cardW = logoWidth + padX * 2
  const cardH = logoHeight + padY * 2
  const radius = 20

  const card = createCanvas(cardW, cardH)
  const ctx = card.getContext('2d')

  // Rounded rect path
  function roundedRect(c, x, y, w, h, r) {
    c.beginPath()
    c.moveTo(x + r, y)
    c.lineTo(x + w - r, y)
    c.quadraticCurveTo(x + w, y, x + w, y + r)
    c.lineTo(x + w, y + h - r)
    c.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
    c.lineTo(x + r, y + h)
    c.quadraticCurveTo(x, y + h, x, y + h - r)
    c.lineTo(x, y + r)
    c.quadraticCurveTo(x, y, x + r, y)
    c.closePath()
  }

  // Card shadow
  ctx.shadowColor = 'rgba(31, 38, 135, 0.2)'
  ctx.shadowBlur = 32
  ctx.shadowOffsetY = 8
  roundedRect(ctx, 0, 0, cardW, cardH, radius)
  ctx.fillStyle = 'rgba(255, 255, 255, 0.15)'
  ctx.fill()
  ctx.shadowColor = 'transparent'

  // Second tint layer
  roundedRect(ctx, 0, 0, cardW, cardH, radius)
  ctx.fillStyle = 'rgba(255, 255, 255, 0.08)'
  ctx.fill()

  // Top highlight gradient
  const hlGrad = ctx.createLinearGradient(0, 0, 0, cardH * 0.5)
  hlGrad.addColorStop(0, 'rgba(255, 255, 255, 0.12)')
  hlGrad.addColorStop(1, 'rgba(255, 255, 255, 0)')
  ctx.save()
  roundedRect(ctx, 0, 0, cardW, cardH, radius)
  ctx.clip()
  ctx.fillStyle = hlGrad
  ctx.fillRect(0, 0, cardW, cardH * 0.5)
  ctx.restore()

  // Top edge line
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(cardW * 0.1, 0.5)
  ctx.lineTo(cardW * 0.9, 0.5)
  ctx.stroke()

  // Border
  roundedRect(ctx, 0.5, 0.5, cardW - 1, cardH - 1, radius)
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)'
  ctx.lineWidth = 1
  ctx.stroke()

  // Logo centered
  ctx.drawImage(logoCanvas, padX, padY)

  return card
}

// ── Entry Point ──────────────────────────────────────────────────────────

async function main() {
  const { inputFile, outputFile, params, wrapCard, cardPadding } = parseArgs(process.argv)

  if (!fs.existsSync(inputFile)) {
    console.error(`File not found: ${inputFile}`)
    process.exit(1)
  }

  let { canvas, width, height } = await glassifyPng(inputFile, params)

  if (wrapCard) {
    canvas = wrapInCard(canvas, width, height, cardPadding)
  }

  const buffer = canvas.toBuffer('image/png')
  fs.writeFileSync(outputFile, buffer)
  console.log(`Output: ${outputFile}`)
  console.log(`Params: ${JSON.stringify(params, null, 2)}`)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
