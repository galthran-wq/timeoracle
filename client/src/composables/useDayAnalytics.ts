import { computed, type Ref } from 'vue'
import type { ActivitySession } from '@/types/activity'
import type { TimelineEntry } from '@/types/timeline'

export function useDayAnalytics(
  sessions: Ref<ActivitySession[]>,
  entries: Ref<TimelineEntry[]>,
) {
  const totalActiveMinutes = computed(() =>
    sessions.value.reduce((sum, s) =>
      sum + (new Date(s.end_time).getTime() - new Date(s.start_time).getTime()) / 60000, 0)
  )

  const sessionCount = computed(() => sessions.value.length)

  const appBreakdown = computed(() => {
    const map = new Map<string, number>()
    for (const s of sessions.value) {
      const mins = (new Date(s.end_time).getTime() - new Date(s.start_time).getTime()) / 60000
      map.set(s.app_name, (map.get(s.app_name) ?? 0) + mins)
    }
    return [...map.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([app, minutes]) => ({ app, minutes }))
  })

  const topApp = computed(() => appBreakdown.value[0]?.app ?? null)

  const categoryBreakdown = computed(() => {
    const map = new Map<string, number>()
    for (const e of entries.value) {
      const cat = e.category ?? 'Uncategorized'
      const mins = (new Date(e.end_time).getTime() - new Date(e.start_time).getTime()) / 60000
      map.set(cat, (map.get(cat) ?? 0) + mins)
    }
    return [...map.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([category, minutes]) => ({ category, minutes }))
  })

  function formatMinutes(mins: number): string {
    const rounded = Math.round(mins)
    if (rounded < 60) return `${rounded}m`
    const h = Math.floor(rounded / 60)
    const m = rounded % 60
    return m > 0 ? `${h}h ${m}m` : `${h}h`
  }

  return { totalActiveMinutes, sessionCount, topApp, appBreakdown, categoryBreakdown, formatMinutes }
}
