export const DEFAULT_ENTRY_COLOR = '#0d7377'

export const CATEGORY_COLORS = [
  '#0d7377', '#2d7a4f', '#b8860b', '#b83230', '#a0522d', '#c2410c', '#0e7490', '#a16207',
]

export const SEMANTIC_COLORS = {
  focusGood: '#2d7a4f',
  focusFair: '#b8860b',
  focusBad: '#b83230',
  deep: '#2d7a4f',
  shallow: '#b8860b',
  reactive: '#b83230',
} as const

export interface SessionColor {
  main: string
  container: string
  onContainer: string
  darkContainer: string
  darkOnContainer: string
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

function rgbToHsl(r: number, g: number, b: number): [number, number, number] {
  r /= 255; g /= 255; b /= 255
  const max = Math.max(r, g, b), min = Math.min(r, g, b)
  const l = (max + min) / 2
  if (max === min) return [0, 0, l]
  const d = max - min
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
  let h = 0
  if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6
  else if (max === g) h = ((b - r) / d + 2) / 6
  else h = ((r - g) / d + 4) / 6
  return [h, s, l]
}

function hslToHex(h: number, s: number, l: number): string {
  const hue2rgb = (p: number, q: number, t: number) => {
    if (t < 0) t += 1; if (t > 1) t -= 1
    if (t < 1/6) return p + (q - p) * 6 * t
    if (t < 1/2) return q
    if (t < 2/3) return p + (q - p) * (2/3 - t) * 6
    return p
  }
  let r: number, g: number, b: number
  if (s === 0) {
    r = g = b = l
  } else {
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s
    const p = 2 * l - q
    r = hue2rgb(p, q, h + 1/3)
    g = hue2rgb(p, q, h)
    b = hue2rgb(p, q, h - 1/3)
  }
  const toHex = (v: number) => Math.round(v * 255).toString(16).padStart(2, '0')
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`
}

const brandColorCache = new Map<string, SessionColor>()

export function sessionColorFromHex(hex: string): SessionColor {
  const cached = brandColorCache.get(hex)
  if (cached) return cached

  const [r, g, b] = hexToRgb(hex)
  const [h, s] = rgbToHsl(r, g, b)

  const color: SessionColor = {
    main: hex,
    container: hslToHex(h, Math.min(s, 0.8), 0.92),
    onContainer: hslToHex(h, Math.min(s, 0.7), 0.18),
    darkContainer: `rgba(${r},${g},${b},0.18)`,
    darkOnContainer: hslToHex(h, Math.min(s, 0.6), 0.82),
  }

  brandColorCache.set(hex, color)
  return color
}

export const SESSION_PALETTE: SessionColor[] = [
  { main: '#0d7377', container: '#ccfbf1', onContainer: '#134E4A', darkContainer: 'rgba(13,115,119,0.18)', darkOnContainer: '#99f6e4' },
  { main: '#2d7a4f', container: '#dcfce7', onContainer: '#14532d', darkContainer: 'rgba(45,122,79,0.18)', darkOnContainer: '#bbf7d0' },
  { main: '#d97706', container: '#fef3c7', onContainer: '#78350F', darkContainer: 'rgba(217,119,6,0.18)', darkOnContainer: '#fde68a' },
  { main: '#c2410c', container: '#ffedd5', onContainer: '#7c2d12', darkContainer: 'rgba(194,65,12,0.18)', darkOnContainer: '#fed7aa' },
  { main: '#a0522d', container: '#fbe8dc', onContainer: '#5c2d14', darkContainer: 'rgba(160,82,45,0.18)', darkOnContainer: '#f0c8a8' },
  { main: '#0e7490', container: '#cffafe', onContainer: '#155e75', darkContainer: 'rgba(14,116,144,0.18)', darkOnContainer: '#a5f3fc' },
  { main: '#b45309', container: '#fef3c7', onContainer: '#78350f', darkContainer: 'rgba(180,83,9,0.18)', darkOnContainer: '#fde68a' },
  { main: '#0d9488', container: '#ccfbf1', onContainer: '#134E4A', darkContainer: 'rgba(13,148,136,0.18)', darkOnContainer: '#99f6e4' },
]
