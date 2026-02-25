import type { ActivitySession } from '@/types/activity'

interface SessionColor {
  main: string
}

interface DayBoundaries {
  start: number
  end: number
}

const LINE_WIDTH = 4
const LANE_GAP = 12
const LANE_STRIDE = LINE_WIDTH + LANE_GAP
const LABEL_STAGGER = 16  // vertical offset per lane to avoid overlap

const MINUTE_MULTIPLIER = 100 / 60

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

    const { assignments, maxLanes } = assignLanes(daySessions)

    const lanesWidth = maxLanes * LANE_STRIDE

    const container = document.createElement('div')
    container.className = 'session-lines-container'
    container.style.cssText = `position:absolute;top:0;left:0;right:0;bottom:0;pointer-events:none;z-index:0;overflow:hidden;`

    for (const { session, lane } of assignments) {
      const colorIdx = appColorMap.get(session.app_name)!
      const color = palette[colorIdx % palette.length].main

      const [startH, startM] = isoToHM(session.start_time)
      const [endH, endM] = isoToHM(session.end_time)

      const topPct = Math.max(0, timeToPercent(startH, startM, dayBounds, pointsPerDay))
      const bottomPct = Math.min(100, timeToPercent(endH, endM, dayBounds, pointsPerDay))
      const heightPct = bottomPct - topPct

      if (heightPct <= 0) continue

      const leftOffset = lane * LANE_STRIDE

      const line = document.createElement('div')
      line.className = 'session-line'
      line.title = session.app_name
      line.style.cssText = `position:absolute;top:${topPct}%;height:${heightPct}%;left:${leftOffset}px;width:${LINE_WIDTH}px;background:${color};border-radius:2px;`

      // Stagger labels vertically per lane so overlapping sessions don't clash
      const labelOffset = lane * LABEL_STAGGER
      const label = document.createElement('div')
      label.className = 'session-line-label'
      label.textContent = session.app_name
      label.style.cssText = `position:absolute;top:calc(${topPct}% + ${labelOffset}px);left:${leftOffset + LINE_WIDTH + 3}px;font-size:12px;line-height:1;color:${color};font-weight:600;white-space:nowrap;max-width:80px;overflow:hidden;text-overflow:ellipsis;`

      container.appendChild(line)
      container.appendChild(label)
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
