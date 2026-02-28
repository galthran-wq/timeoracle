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
