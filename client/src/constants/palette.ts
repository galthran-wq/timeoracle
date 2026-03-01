export const DEFAULT_ENTRY_COLOR = '#3B82F6'

export const CATEGORY_COLORS = [
  '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#6366F1', '#14B8A6',
]

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
  { main: '#6366F1', container: '#E0E7FF', onContainer: '#312E81', darkContainer: 'rgba(99,102,241,0.18)', darkOnContainer: '#C7D2FE' },
  { main: '#14B8A6', container: '#CCFBF1', onContainer: '#134E4A', darkContainer: 'rgba(20,184,166,0.18)', darkOnContainer: '#99F6E4' },
  { main: '#F59E0B', container: '#FEF3C7', onContainer: '#78350F', darkContainer: 'rgba(245,158,11,0.18)', darkOnContainer: '#FDE68A' },
  { main: '#EC4899', container: '#FCE7F3', onContainer: '#831843', darkContainer: 'rgba(236,72,153,0.18)', darkOnContainer: '#FBCFE8' },
  { main: '#8B5CF6', container: '#EDE9FE', onContainer: '#4C1D95', darkContainer: 'rgba(139,92,246,0.18)', darkOnContainer: '#DDD6FE' },
  { main: '#10B981', container: '#D1FAE5', onContainer: '#064E3B', darkContainer: 'rgba(16,185,129,0.18)', darkOnContainer: '#A7F3D0' },
  { main: '#F97316', container: '#FFEDD5', onContainer: '#7C2D12', darkContainer: 'rgba(249,115,22,0.18)', darkOnContainer: '#FED7AA' },
  { main: '#06B6D4', container: '#CFFAFE', onContainer: '#155E75', darkContainer: 'rgba(6,182,212,0.18)', darkOnContainer: '#A5F3FC' },
]
