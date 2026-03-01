import type { ActivitySession } from '@/types/activity'
import { sessionColorFromHex, type SessionColor } from '@/constants/palette'

interface DayBoundaries {
  start: number
  end: number
}

const STRIP_WIDTH = 40
const MIN_HEIGHT_FOR_INITIAL = 7 // minutes

const MINUTE_MULTIPLIER = 100 / 60

function applyAlpha(color: string, alpha: number): string {
  const trimmed = color.trim()
  const rgbaMatch = trimmed.match(/^rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+)\s*\)$/)
  if (rgbaMatch) {
    const a = Math.max(0, Math.min(1, Number(rgbaMatch[4]) * alpha))
    return `rgba(${rgbaMatch[1]}, ${rgbaMatch[2]}, ${rgbaMatch[3]}, ${a})`
  }
  const rgbMatch = trimmed.match(/^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$/)
  if (rgbMatch) {
    return `rgba(${rgbMatch[1]}, ${rgbMatch[2]}, ${rgbMatch[3]}, ${alpha})`
  }
  if (trimmed.startsWith('#')) {
    let hex = trimmed.slice(1)
    if (hex.length === 3) {
      hex = hex.split('').map((c) => c + c).join('')
    }
    if (hex.length === 6) {
      const r = Number.parseInt(hex.slice(0, 2), 16)
      const g = Number.parseInt(hex.slice(2, 4), 16)
      const b = Number.parseInt(hex.slice(4, 6), 16)
      return `rgba(${r}, ${g}, ${b}, ${alpha})`
    }
  }
  return color
}

function timePointsFromHM(hours: number, minutes: number): number {
  let minutePoints = (minutes * MINUTE_MULTIPLIER).toString()
  if (minutePoints.split('.')[0].length < 2) minutePoints = '0' + minutePoints
  return Number(String(hours) + minutePoints)
}

function isoToLocalDate(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function isoToHM(iso: string): [number, number] {
  const d = new Date(iso)
  return [d.getHours(), d.getMinutes()]
}

function timeToPercent(
  hours: number,
  minutes: number,
  dayBounds: DayBoundaries,
  pointsPerDay: number,
): number {
  const tp = timePointsFromHM(hours, minutes)
  if (tp < dayBounds.start) {
    const firstDayPoints = 2400 - dayBounds.start
    return ((tp + firstDayPoints) / pointsPerDay) * 100
  }
  return ((tp - dayBounds.start) / pointsPerDay) * 100
}

interface LaneAssignment {
  session: ActivitySession
  lane: number
}

function assignLanes(sessions: ActivitySession[]): { assignments: LaneAssignment[]; maxLanes: number } {
  if (!sessions.length) return { assignments: [], maxLanes: 0 }

  const sorted = [...sessions].sort(
    (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime(),
  )

  const laneEnds: number[] = []
  const assignments: LaneAssignment[] = []

  for (const session of sorted) {
    const startMs = new Date(session.start_time).getTime()
    const endMs = new Date(session.end_time).getTime()

    let assigned = -1
    for (let i = 0; i < laneEnds.length; i++) {
      if (laneEnds[i] <= startMs) {
        assigned = i
        break
      }
    }

    if (assigned === -1) {
      assigned = laneEnds.length
      laneEnds.push(endMs)
    } else {
      laneEnds[assigned] = endMs
    }

    assignments.push({ session, lane: assigned })
  }

  return { assignments, maxLanes: laneEnds.length }
}

function buildAppColorMap(sessions: ActivitySession[]): Map<string, number> {
  const map = new Map<string, number>()
  let idx = 0
  for (const s of sessions) {
    if (!map.has(s.app_name)) {
      map.set(s.app_name, idx++)
    }
  }
  return map
}

function sessionDurationMinutes(session: ActivitySession): number {
  return (new Date(session.end_time).getTime() - new Date(session.start_time).getTime()) / 60000
}

export function createSessionLinesPlugin(palette: SessionColor[]) {
  let $app: any = null
  let sessions: ActivitySession[] = []
  let enabled = true
  let observer: MutationObserver | null = null
  const injectedContainers = new Map<string, HTMLElement>()
  let rafId: number | null = null
  let rendering = false

  function getWrapper(): HTMLElement | null {
    return $app?.elements?.calendarWrapper ?? null
  }

  function getDayBounds(): DayBoundaries {
    return $app.config.dayBoundaries.value
  }

  function getPointsPerDay(): number {
    return $app.config.timePointsPerDay
  }

  function scheduleRender() {
    if (rafId !== null) return
    rafId = requestAnimationFrame(() => {
      rafId = null
      renderAllDays()
    })
  }

  function renderAllDays() {
    const wrapper = getWrapper()
    if (!wrapper) return

    rendering = true

    const dayColumns = wrapper.querySelectorAll<HTMLElement>('.sx__time-grid-day[data-time-grid-date]')
    const visibleDates = new Set<string>()

    const byDate = new Map<string, ActivitySession[]>()
    if (enabled) {
      for (const s of sessions) {
        const dateStr = s.date || isoToLocalDate(s.start_time)
        if (!byDate.has(dateStr)) byDate.set(dateStr, [])
        byDate.get(dateStr)!.push(s)
      }
    }

    const appColorMap = buildAppColorMap(sessions)

    for (const dayCol of dayColumns) {
      const dateStr = dayCol.getAttribute('data-time-grid-date')!
      visibleDates.add(dateStr)

      const daySessions = byDate.get(dateStr) ?? []
      renderDayColumn(dayCol, dateStr, daySessions, appColorMap)
    }

    for (const [dateStr, container] of injectedContainers) {
      if (!visibleDates.has(dateStr)) {
        container.remove()
        injectedContainers.delete(dateStr)
      }
    }

    rendering = false
  }

  function isDark(): boolean {
    try {
      return $app?.config?.isDark?.value ?? false
    } catch {
      return false
    }
  }

  function renderDayColumn(
    dayEl: HTMLElement,
    dateStr: string,
    daySessions: ActivitySession[],
    appColorMap: Map<string, number>,
  ) {
    const old = injectedContainers.get(dateStr)
    if (old) {
      old.remove()
      injectedContainers.delete(dateStr)
    }

    if (!daySessions.length || !enabled) return

    const dayBounds = getDayBounds()
    const pointsPerDay = getPointsPerDay()
    const dark = isDark()

    const { assignments } = assignLanes(daySessions)

    const container = document.createElement('div')
    container.className = 'session-lines-container'
    container.style.cssText = `position:absolute;top:0;left:0;right:0;bottom:0;pointer-events:none;z-index:3;overflow:hidden;`

    for (const { session, lane } of assignments) {
      const color = session.brand_color
        ? sessionColorFromHex(session.brand_color)
        : palette[appColorMap.get(session.app_name)! % palette.length]

      const [startH, startM] = isoToHM(session.start_time)
      const [endH, endM] = isoToHM(session.end_time)

      const topPct = Math.max(0, timeToPercent(startH, startM, dayBounds, pointsPerDay))
      const bottomPct = Math.min(100, timeToPercent(endH, endM, dayBounds, pointsPerDay))
      const heightPct = bottomPct - topPct

      if (heightPct <= 0) continue

      const leftOffset = lane * STRIP_WIDTH
      const stripOpacity = dark ? 0.6 : 0.75
      const bg = applyAlpha(dark ? color.darkContainer : color.container, stripOpacity)

      const strip = document.createElement('div')
      strip.className = 'session-strip'
      strip.title = session.app_name
      strip.style.cssText = [
        'position:absolute',
        `top:${topPct}%`,
        `height:${heightPct}%`,
        `left:${leftOffset}px`,
        `width:${STRIP_WIDTH}px`,
        `background:${bg}`,
        `border-left:3px solid ${color.main}`,
        'border-radius:2px',
        'box-sizing:border-box',
        'pointer-events:auto',
        'cursor:default',
      ].join(';') + ';'

      const appendInitial = (parent: HTMLElement) => {
        if (sessionDurationMinutes(session) >= MIN_HEIGHT_FOR_INITIAL) {
          const textColor = dark ? color.darkOnContainer : color.onContainer
          const initial = document.createElement('div')
          initial.textContent = session.app_name.charAt(0).toUpperCase()
          initial.style.cssText = [
            'text-align:center',
            'margin-top:4px',
            'font-size:14px',
            'font-weight:600',
            'line-height:1',
            `color:${textColor}`,
            'pointer-events:none',
            'user-select:none',
          ].join(';') + ';'
          parent.appendChild(initial)
        }
      }

      if (session.icon) {
        const img = document.createElement('img')
        img.src = session.icon
        img.width = 16
        img.height = 16
        img.style.cssText = 'display:block;margin:4px auto 0;pointer-events:none;'
        img.onerror = () => {
          img.remove()
          appendInitial(strip)
        }
        strip.appendChild(img)
      } else {
        appendInitial(strip)
      }

      container.appendChild(strip)
    }

    dayEl.appendChild(container)
    injectedContainers.set(dateStr, container)
  }

  return {
    name: 'sessionLines' as const,

    beforeRender(app: any) {
      $app = app
    },

    onRender() {
      renderAllDays()

      const wrapper = getWrapper()
      if (wrapper) {
        observer = new MutationObserver(() => {
          if (rendering) return
          let needsRerender = false
          for (const [dateStr, container] of injectedContainers) {
            if (!container.isConnected) {
              injectedContainers.delete(dateStr)
              needsRerender = true
            }
          }
          if (needsRerender || injectedContainers.size === 0) {
            scheduleRender()
          }
        })
        observer.observe(wrapper, { childList: true, subtree: true })
      }
    },

    onRangeUpdate() {
      scheduleRender()
    },

    setSessions(newSessions: ActivitySession[]) {
      sessions = newSessions
      scheduleRender()
    },

    setEnabled(value: boolean) {
      enabled = value
      scheduleRender()
    },

    destroy() {
      if (observer) {
        observer.disconnect()
        observer = null
      }
      if (rafId !== null) {
        cancelAnimationFrame(rafId)
        rafId = null
      }
      for (const container of injectedContainers.values()) {
        container.remove()
      }
      injectedContainers.clear()
      $app = null
    },
  }
}
