/**
 * Liquid Glass Design System — React Components
 * 
 * Pure CSS implementation (no library dependencies).
 * Requires liquid-glass.css loaded in the document.
 * 
 * For full SVG distortion/refraction, use liquid-glass-react (npm)
 * or @developer-hub/liquid-glass (npm) instead.
 */

import React, { forwardRef } from 'react'

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

type GlassVariant = 'frosted' | 'translucent' | 'prominent' | 'tinted' | 'dark'
type GlassRadius = 'sm' | 'md' | 'lg' | 'pill'

interface GlassContainerProps extends React.HTMLAttributes<HTMLElement> {
  /** Visual variant */
  variant?: GlassVariant
  /** Border radius preset */
  radius?: GlassRadius
  /** Make hoverable/clickable with state transitions */
  interactive?: boolean
  /** Override tint color (used with variant="tinted") */
  tintColor?: string
  /** Render as a different HTML element */
  as?: React.ElementType
  children: React.ReactNode
}

interface GlassCardProps extends GlassContainerProps {
  /** Card padding */
  padding?: string | number
}

interface GlassButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: GlassVariant
  /** Pill shape by default */
  radius?: GlassRadius
  children: React.ReactNode
}

interface GlassNavProps extends React.HTMLAttributes<HTMLElement> {
  /** Position: fixed top or bottom */
  position?: 'top' | 'bottom'
  children: React.ReactNode
}

/* ------------------------------------------------------------------ */
/* GlassContainer — Base                                               */
/* ------------------------------------------------------------------ */

export const GlassContainer = forwardRef<HTMLElement, GlassContainerProps>(
  (
    {
      variant,
      radius = 'md',
      interactive = false,
      tintColor,
      as: Tag = 'div',
      className = '',
      style,
      children,
      ...rest
    },
    ref
  ) => {
    const classes = [
      'glass',
      variant && `glass--${variant}`,
      radius !== 'md' && `glass--${radius}`,
      interactive && 'glass--interactive',
      className,
    ]
      .filter(Boolean)
      .join(' ')

    const mergedStyle: React.CSSProperties = {
      ...(tintColor
        ? ({ '--glass-tint-primary': tintColor } as React.CSSProperties)
        : {}),
      ...style,
    }

    return (
      <Tag ref={ref} className={classes} style={mergedStyle} {...rest}>
        {children}
      </Tag>
    )
  }
)
GlassContainer.displayName = 'GlassContainer'

/* ------------------------------------------------------------------ */
/* GlassCard — Padded content card                                     */
/* ------------------------------------------------------------------ */

export const GlassCard = forwardRef<HTMLElement, GlassCardProps>(
  ({ padding = '24px', style, children, ...rest }, ref) => (
    <GlassContainer
      ref={ref}
      style={{ padding, ...style }}
      {...rest}
    >
      {children}
    </GlassContainer>
  )
)
GlassCard.displayName = 'GlassCard'

/* ------------------------------------------------------------------ */
/* GlassButton — Interactive pill button                               */
/* ------------------------------------------------------------------ */

export const GlassButton = forwardRef<HTMLButtonElement, GlassButtonProps>(
  (
    {
      variant = 'prominent',
      radius = 'pill',
      className = '',
      children,
      ...rest
    },
    ref
  ) => {
    const classes = [
      'glass',
      'glass--interactive',
      variant && `glass--${variant}`,
      `glass--${radius}`,
      className,
    ]
      .filter(Boolean)
      .join(' ')

    return (
      <button ref={ref} className={classes} {...rest}>
        {children}
      </button>
    )
  }
)
GlassButton.displayName = 'GlassButton'

/* ------------------------------------------------------------------ */
/* GlassNav — Fixed navigation bar                                     */
/* ------------------------------------------------------------------ */

export const GlassNav = forwardRef<HTMLElement, GlassNavProps>(
  ({ position = 'top', className = '', style, children, ...rest }, ref) => {
    const positionStyles: React.CSSProperties =
      position === 'top'
        ? { position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50 }
        : { position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 50 }

    return (
      <nav
        ref={ref}
        className={`glass glass--frosted ${className}`}
        style={{
          ...positionStyles,
          borderRadius: 0,
          ...style,
        }}
        {...rest}
      >
        {children}
      </nav>
    )
  }
)
GlassNav.displayName = 'GlassNav'

/* ------------------------------------------------------------------ */
/* GlassRefractionSVG — Hidden SVG filter for distortion               */
/*                                                                     */
/* Mount once at app root. Reference via CSS:                          */
/*   backdrop-filter: blur(8px) url(#glass-refraction);                */
/*                                                                     */
/* Chromium-only. Safari/Firefox get blur-only fallback automatically. */
/* ------------------------------------------------------------------ */

interface GlassRefractionSVGProps {
  /** Noise frequency (lower = larger distortion waves) */
  baseFrequency?: number
  /** Noise complexity */
  octaves?: number
  /** Displacement intensity */
  scale?: number
  /** Noise softening */
  stdDeviation?: number
  /** Filter ID for CSS reference */
  filterId?: string
}

export function GlassRefractionSVG({
  baseFrequency = 0.008,
  octaves = 2,
  scale = 60,
  stdDeviation = 2,
  filterId = 'glass-refraction',
}: GlassRefractionSVGProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="0"
      height="0"
      style={{ position: 'absolute', overflow: 'hidden' }}
      aria-hidden="true"
    >
      <defs>
        <filter id={filterId} x="0%" y="0%" width="100%" height="100%">
          <feTurbulence
            type="fractalNoise"
            baseFrequency={`${baseFrequency} ${baseFrequency}`}
            numOctaves={octaves}
            seed={42}
            result="noise"
          />
          <feGaussianBlur
            in="noise"
            stdDeviation={stdDeviation}
            result="softNoise"
          />
          <feDisplacementMap
            in="SourceGraphic"
            in2="softNoise"
            scale={scale}
            xChannelSelector="R"
            yChannelSelector="G"
          />
        </filter>
      </defs>
    </svg>
  )
}
