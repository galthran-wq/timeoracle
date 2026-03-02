function toLocalParts(dt: Date, tz: string): { year: number; month: number; day: number; hour: number } {
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone: tz,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    hour12: false,
  })
  const parts = Object.fromEntries(fmt.formatToParts(dt).map((p) => [p.type, p.value]))
  return {
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
    hour: Number(parts.hour === '24' ? '0' : parts.hour),
  }
}

function pad(n: number): string {
  return n.toString().padStart(2, '0')
}

export function getLogicalToday(dayStartHour: number, timezone: string): string {
  const now = new Date()
  const local = toLocalParts(now, timezone)
  let year = local.year
  let month = local.month
  let day = local.day
  if (local.hour < dayStartHour) {
    const prev = new Date(now.getTime() - 86400000)
    const p = toLocalParts(prev, timezone)
    year = p.year
    month = p.month
    day = p.day
  }
  return `${year}-${pad(month)}-${pad(day)}`
}
