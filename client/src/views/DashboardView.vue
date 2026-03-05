<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue'
import {
  NSpace,
  NButton,
  NButtonGroup,
  NList,
  NListItem,
  NText,
  NCard,
  NSpin,
  NEmpty,
  NTooltip,
  NDatePicker,
  NSelect,
} from 'naive-ui'
import { useRouter } from 'vue-router'
import { format, subDays, addDays, subMonths, addMonths, startOfWeek, endOfWeek, startOfMonth, endOfMonth } from 'date-fns'
import { formatDistanceToNow } from 'date-fns'
import { useActivityStore } from '@/stores/activity'
import { useAuthStore } from '@/stores/auth'
import { listEntries } from '@/api/timeline'
import { getDaySummary, getDaySummaryTrends } from '@/api/daySummary'
import { getProductivityCurve, getAggregatedCurve } from '@/api/productivityCurve'
import { usePolling } from '@/composables/usePolling'
import { SEMANTIC_COLORS } from '@/constants/palette'
import { getLogicalToday } from '@/utils/dayBoundary'
import ProductivityCurve from '@/components/ProductivityCurve.vue'
import CategoryBreakdownChart from '@/components/CategoryBreakdownChart.vue'
import type { TimelineEntry } from '@/types/timeline'
import type { DaySummary } from '@/types/daySummary'
import type { ProductivityCurveResponse, AggregatedCurveResponse } from '@/types/productivityCurve'

const router = useRouter()
const activityStore = useActivityStore()
const loading = ref(true)
const showAllEntries = ref(false)

const entries = ref<TimelineEntry[]>([])
const daySummary = ref<DaySummary | null>(null)
const dayCurve = ref<ProductivityCurveResponse | null>(null)
const aggregatedCurve = ref<AggregatedCurveResponse | null>(null)
const periodSummaries = ref<DaySummary[]>([])

type PeriodMode = 'day' | 'week' | 'month'
const periodMode = ref<PeriodMode>('day')

const authStore = useAuthStore()
const cfg = authStore.user?.session_config
const logicalToday = cfg ? getLogicalToday(cfg.day_start_hour, cfg.timezone) : format(new Date(), 'yyyy-MM-dd')
const selectedDate = ref(logicalToday)

const DEFAULT_BUCKET: Record<PeriodMode, number> = { day: 10, week: 360, month: 1440 }
const BUCKET_OPTIONS: Record<PeriodMode, { label: string; value: number }[]> = {
  day: [{ label: '10 min', value: 10 }],
  week: [
    { label: '1 hour', value: 60 },
    { label: '3 hours', value: 180 },
    { label: '6 hours', value: 360 },
  ],
  month: [
    { label: '6 hours', value: 360 },
    { label: '1 day', value: 1440 },
  ],
}
const bucketMinutes = ref(DEFAULT_BUCKET.day)

const dateRange = computed(() => {
  const d = new Date(selectedDate.value + 'T00:00:00')
  if (periodMode.value === 'day') {
    return { start: selectedDate.value, end: selectedDate.value }
  }
  if (periodMode.value === 'week') {
    const s = startOfWeek(d, { weekStartsOn: 1 })
    const e = endOfWeek(d, { weekStartsOn: 1 })
    return { start: format(s, 'yyyy-MM-dd'), end: format(e, 'yyyy-MM-dd') }
  }
  const s = startOfMonth(d)
  const e = endOfMonth(d)
  return { start: format(s, 'yyyy-MM-dd'), end: format(e, 'yyyy-MM-dd') }
})

const isActive = computed(() => {
  if (!activityStore.status?.last_event_at) return false
  return Date.now() - new Date(activityStore.status.last_event_at).getTime() < 5 * 60 * 1000
})

const lastEventText = computed(() => {
  if (!activityStore.status?.last_event_at) return 'No events yet'
  return formatDistanceToNow(new Date(activityStore.status.last_event_at), { addSuffix: true })
})

const displayedEntries = computed(() =>
  showAllEntries.value ? entries.value : entries.value.slice(0, 8)
)

const curveScores = computed(() => {
  if (periodMode.value === 'day' && dayCurve.value) {
    return {
      productivity: dayCurve.value.overall_score,
      performance: dayCurve.value.day_score,
      workMinutes: dayCurve.value.work_minutes,
    }
  }
  if (aggregatedCurve.value) {
    return {
      productivity: aggregatedCurve.value.overall_score,
      performance: aggregatedCurve.value.performance_score,
      workMinutes: null,
    }
  }
  return { productivity: null, performance: null, workMinutes: null }
})

const metrics = computed(() => {
  if (periodMode.value === 'day') {
    const s = daySummary.value
    if (!s) return null
    return {
      activeTime: s.total_active_minutes,
      deepWork: s.deep_work_minutes,
      avgFocus: s.avg_focus_score,
      longestFocus: s.longest_focus_minutes,
      contextSwitches: s.context_switches,
      workMinutes: s.work_minutes,
      productivity: s.overall_productivity_score,
      performance: s.productivity_score,
    }
  }
  if (!periodSummaries.value.length) return null
  const sums = periodSummaries.value.reduce(
    (acc, s) => ({
      activeTime: acc.activeTime + s.total_active_minutes,
      deepWork: acc.deepWork + s.deep_work_minutes,
      longestFocus: Math.max(acc.longestFocus, s.longest_focus_minutes),
      contextSwitches: acc.contextSwitches + s.context_switches,
      workMinutes: acc.workMinutes + s.work_minutes,
      focusSum: acc.focusSum + (s.avg_focus_score ?? 0),
      focusCount: acc.focusCount + (s.avg_focus_score !== null ? 1 : 0),
      prodSum: acc.prodSum + (s.overall_productivity_score ?? 0),
      prodCount: acc.prodCount + (s.overall_productivity_score !== null ? 1 : 0),
      perfSum: acc.perfSum + (s.productivity_score ?? 0),
      perfCount: acc.perfCount + (s.productivity_score !== null ? 1 : 0),
    }),
    { activeTime: 0, deepWork: 0, longestFocus: 0, contextSwitches: 0, workMinutes: 0, focusSum: 0, focusCount: 0, prodSum: 0, prodCount: 0, perfSum: 0, perfCount: 0 },
  )
  return {
    activeTime: sums.activeTime,
    deepWork: sums.deepWork,
    avgFocus: sums.focusCount ? sums.focusSum / sums.focusCount : null,
    longestFocus: sums.longestFocus,
    contextSwitches: sums.contextSwitches,
    workMinutes: sums.workMinutes,
    productivity: sums.prodCount ? Math.round((sums.prodSum / sums.prodCount) * 10) / 10 : null,
    performance: sums.perfCount ? Math.round((sums.perfSum / sums.perfCount) * 10) / 10 : null,
  }
})

const narrative = computed(() => {
  if (periodMode.value === 'day') return daySummary.value?.narrative ?? null
  const latest = periodSummaries.value.filter((s) => s.narrative).pop()
  return latest?.narrative ?? null
})

const CATEGORY_COLOR_MAP: Record<string, string> = {
  Work: '#3B82F6',
  Communication: '#8B5CF6',
  Research: '#F59E0B',
  Entertainment: '#EF4444',
  Health: '#10B981',
  Personal: '#EC4899',
  Admin: '#6B7280',
}

const categoryBreakdown = computed(() => {
  const timeMap = new Map<string, number>()
  const items = periodMode.value === 'day'
    ? (daySummary.value?.category_breakdown ?? [])
    : periodSummaries.value.flatMap((s) => s.category_breakdown ?? [])
  for (const item of items) {
    timeMap.set(item.category, (timeMap.get(item.category) ?? 0) + item.minutes)
  }

  const scoreMap = new Map<string, { sum: number; count: number }>()
  const points = periodMode.value === 'day'
    ? (dayCurve.value?.points ?? [])
    : (aggregatedCurve.value?.buckets ?? []).map((b) => ({ category: b.dominant_category, productivity_score: b.avg_productivity_score }))
  for (const p of points) {
    const cat = p.category
    if (!cat || p.productivity_score == null) continue
    const prev = scoreMap.get(cat) ?? { sum: 0, count: 0 }
    prev.sum += p.productivity_score
    prev.count += 1
    scoreMap.set(cat, prev)
  }

  return [...timeMap.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([category, minutes]) => {
      const s = scoreMap.get(category)
      return {
        category,
        minutes,
        avgScore: s ? Math.round((s.sum / s.count) * 10) / 10 : null,
        color: CATEGORY_COLOR_MAP[category] ?? '#6B7280',
      }
    })
})

const prevDaySummary = ref<DaySummary | null>(null)
const prevPeriodSummaries = ref<DaySummary[]>([])

const prevDateRange = computed(() => {
  const d = new Date(selectedDate.value + 'T00:00:00')
  if (periodMode.value === 'day') {
    const prev = format(subDays(d, 1), 'yyyy-MM-dd')
    return { start: prev, end: prev }
  }
  if (periodMode.value === 'week') {
    const s = startOfWeek(subDays(startOfWeek(d, { weekStartsOn: 1 }), 1), { weekStartsOn: 1 })
    const e = endOfWeek(s, { weekStartsOn: 1 })
    return { start: format(s, 'yyyy-MM-dd'), end: format(e, 'yyyy-MM-dd') }
  }
  const prev = subMonths(startOfMonth(d), 1)
  return { start: format(startOfMonth(prev), 'yyyy-MM-dd'), end: format(endOfMonth(prev), 'yyyy-MM-dd') }
})

const prevMetrics = computed(() => {
  if (periodMode.value === 'day') {
    const s = prevDaySummary.value
    if (!s) return null
    return {
      activeTime: s.total_active_minutes,
      deepWork: s.deep_work_minutes,
      avgFocus: s.avg_focus_score,
      longestFocus: s.longest_focus_minutes,
      contextSwitches: s.context_switches,
      workMinutes: s.work_minutes,
      productivity: s.overall_productivity_score,
      performance: s.productivity_score,
    }
  }
  if (!prevPeriodSummaries.value.length) return null
  const sums = prevPeriodSummaries.value.reduce(
    (acc, s) => ({
      activeTime: acc.activeTime + s.total_active_minutes,
      deepWork: acc.deepWork + s.deep_work_minutes,
      longestFocus: Math.max(acc.longestFocus, s.longest_focus_minutes),
      contextSwitches: acc.contextSwitches + s.context_switches,
      workMinutes: acc.workMinutes + s.work_minutes,
      focusSum: acc.focusSum + (s.avg_focus_score ?? 0),
      focusCount: acc.focusCount + (s.avg_focus_score !== null ? 1 : 0),
      prodSum: acc.prodSum + (s.overall_productivity_score ?? 0),
      prodCount: acc.prodCount + (s.overall_productivity_score !== null ? 1 : 0),
      perfSum: acc.perfSum + (s.productivity_score ?? 0),
      perfCount: acc.perfCount + (s.productivity_score !== null ? 1 : 0),
    }),
    { activeTime: 0, deepWork: 0, longestFocus: 0, contextSwitches: 0, workMinutes: 0, focusSum: 0, focusCount: 0, prodSum: 0, prodCount: 0, perfSum: 0, perfCount: 0 },
  )
  return {
    activeTime: sums.activeTime,
    deepWork: sums.deepWork,
    avgFocus: sums.focusCount ? sums.focusSum / sums.focusCount : null,
    longestFocus: sums.longestFocus,
    contextSwitches: sums.contextSwitches,
    workMinutes: sums.workMinutes,
    productivity: sums.prodCount ? Math.round((sums.prodSum / sums.prodCount) * 10) / 10 : null,
    performance: sums.perfCount ? Math.round((sums.perfSum / sums.perfCount) * 10) / 10 : null,
  }
})

const TIME_SLOTS = ['00–06', '06–12', '12–18', '18–24']
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

interface HeatmapGrid {
  columns: string[]
  rows: string[]
  cells: (number | null)[][]
  labels: Map<string, string>
}

const heatmapGrid = computed((): HeatmapGrid | null => {
  if (periodMode.value === 'day') return null

  const bucketMap = new Map<string, number | null>()
  if (aggregatedCurve.value) {
    for (const b of aggregatedCurve.value.buckets) {
      const d = new Date(b.bucket_start)
      const key = format(d, 'yyyy-MM-dd') + '-' + d.getHours()
      bucketMap.set(key, b.avg_productivity_score)
    }
  }

  const scoreMap = new Map<string, number | null>()
  for (const s of periodSummaries.value) {
    scoreMap.set(s.date, s.overall_productivity_score ?? s.productivity_score)
  }

  const { start, end } = dateRange.value
  const labelMap = new Map<string, string>()

  if (periodMode.value === 'week') {
    const cells: (number | null)[][] = []
    for (let row = 0; row < 4; row++) {
      cells.push([])
    }
    let d = new Date(start + 'T00:00:00')
    const endD = new Date(end + 'T00:00:00')
    const columns: string[] = []
    while (d <= endD) {
      const dateStr = format(d, 'yyyy-MM-dd')
      columns.push(format(d, 'EEE'))
      for (let slot = 0; slot < 4; slot++) {
        const hour = slot * 6
        const key = dateStr + '-' + hour
        const score = bucketMap.get(key) ?? null
        cells[slot].push(score)
        const cellKey = `${slot}-${columns.length - 1}`
        const slotLabel = TIME_SLOTS[slot]
        labelMap.set(cellKey, `${format(d, 'EEE, MMM d')} ${slotLabel}`)
      }
      d = addDays(d, 1)
    }
    return { columns, rows: TIME_SLOTS, cells, labels: labelMap }
  }

  const firstDay = new Date(start + 'T00:00:00')
  const lastDay = new Date(end + 'T00:00:00')
  const weeks: Date[][] = []
  let weekStart = startOfWeek(firstDay, { weekStartsOn: 1 })
  while (weekStart <= lastDay) {
    const week: Date[] = []
    for (let i = 0; i < 7; i++) {
      week.push(addDays(weekStart, i))
    }
    weeks.push(week)
    weekStart = addDays(weekStart, 7)
  }

  const rows = weeks.map((w) => format(w[0], 'MMM d'))
  const cells: (number | null)[][] = []
  for (const week of weeks) {
    const row: (number | null)[] = []
    for (const day of week) {
      const dateStr = format(day, 'yyyy-MM-dd')
      if (day < firstDay || day > lastDay) {
        row.push(null)
      } else {
        row.push(scoreMap.get(dateStr) ?? null)
      }
      const cellKey = `${cells.length}-${row.length - 1}`
      labelMap.set(cellKey, format(day, 'EEE, MMM d'))
    }
    cells.push(row)
  }
  return { columns: WEEKDAYS, rows, cells, labels: labelMap }
})

function heatmapColor(score: number | null): string {
  if (score === null) return 'rgba(150,150,150,0.15)'
  const t = score / 100
  if (t < 0.3) return `rgba(239,68,68,${0.3 + t})`
  if (t < 0.6) return `rgba(234,179,8,${0.3 + t * 0.5})`
  return `rgba(34,197,94,${0.3 + t * 0.5})`
}

function formatMinutes(mins: number): string {
  const rounded = Math.round(mins)
  const absMinutes = Math.abs(rounded)
  if (absMinutes < 60) return `${rounded}m`
  const h = Math.floor(absMinutes / 60)
  const m = absMinutes % 60
  const sign = rounded < 0 ? '-' : ''
  return m > 0 ? `${sign}${h}h ${m}m` : `${sign}${h}h`
}

function formatScore(score: number | null): string {
  if (score === null) return '\u2014'
  return Math.round(score * 100) + '%'
}

function focusScoreColor(score: number | null): string {
  if (score === null) return 'var(--to-text-secondary)'
  if (score > 0.6) return SEMANTIC_COLORS.focusGood
  if (score >= 0.3) return SEMANTIC_COLORS.focusFair
  return SEMANTIC_COLORS.focusBad
}

function navigateDate(dir: -1 | 1) {
  const d = new Date(selectedDate.value + 'T00:00:00')
  if (periodMode.value === 'day') {
    selectedDate.value = format(dir === -1 ? subDays(d, 1) : addDays(d, 1), 'yyyy-MM-dd')
  } else if (periodMode.value === 'week') {
    selectedDate.value = format(dir === -1 ? subDays(d, 7) : addDays(d, 7), 'yyyy-MM-dd')
  } else {
    selectedDate.value = format(dir === -1 ? subMonths(d, 1) : addMonths(d, 1), 'yyyy-MM-dd')
  }
}

function goToday() {
  selectedDate.value = logicalToday
}

function setPeriod(mode: PeriodMode) {
  periodMode.value = mode
  bucketMinutes.value = DEFAULT_BUCKET[mode]
}

const periodLabel = computed(() => {
  const d = new Date(selectedDate.value + 'T00:00:00')
  if (periodMode.value === 'day') return format(d, 'EEE, MMM d')
  if (periodMode.value === 'week') {
    const r = dateRange.value
    return `${format(new Date(r.start + 'T00:00:00'), 'MMM d')} \u2013 ${format(new Date(r.end + 'T00:00:00'), 'MMM d')}`
  }
  return format(d, 'MMMM yyyy')
})

async function refreshAll() {
  const { start, end } = dateRange.value
  const prev = prevDateRange.value
  const promises: Promise<void>[] = [activityStore.fetchStatus()]

  if (periodMode.value === 'day') {
    promises.push(
      listEntries({ date: start }).then((res) => { entries.value = res.entries }),
      getDaySummary(start).then((s) => { daySummary.value = s }).catch(() => { daySummary.value = null }),
      getProductivityCurve(start).then((c) => { dayCurve.value = c }).catch(() => { dayCurve.value = null }),
      getDaySummary(prev.start).then((s) => { prevDaySummary.value = s }).catch(() => { prevDaySummary.value = null }),
    )
    aggregatedCurve.value = null
    periodSummaries.value = []
    prevPeriodSummaries.value = []
  } else {
    const entryRange = periodMode.value === 'week' ? 'week' : undefined
    promises.push(
      getDaySummaryTrends(start, end).then((r) => { periodSummaries.value = r.summaries }).catch(() => { periodSummaries.value = [] }),
      getAggregatedCurve(start, end, bucketMinutes.value).then((c) => { aggregatedCurve.value = c }).catch(() => { aggregatedCurve.value = null }),
      listEntries({ date: selectedDate.value, range: entryRange }).then((res) => { entries.value = res.entries }).catch(() => { entries.value = [] }),
      getDaySummaryTrends(prev.start, prev.end).then((r) => { prevPeriodSummaries.value = r.summaries }).catch(() => { prevPeriodSummaries.value = [] }),
    )
    dayCurve.value = null
    daySummary.value = null
    prevDaySummary.value = null
  }

  await Promise.all(promises)
}

watch([selectedDate, periodMode, bucketMinutes], () => {
  loading.value = true
  refreshAll().finally(() => { loading.value = false })
})

onMounted(async () => {
  await refreshAll()
  loading.value = false
})

usePolling(refreshAll, 60_000)

function formatDelta(key: string, curr: number, prev: number): string {
  const diff = curr - prev
  if (Math.abs(diff) < 0.1) return ''
  const sign = diff > 0 ? '+' : ''
  if (['activeTime', 'deepWork', 'longestFocus', 'workMinutes'].includes(key)) return sign + formatMinutes(diff)
  if (key === 'avgFocus') return sign + Math.round(diff * 100) + '%'
  return sign + Math.round(diff).toString()
}

function deltaColor(key: string, diff: number): string {
  if (Math.abs(diff) < 0.1) return 'transparent'
  const positive = diff > 0
  if (key === 'contextSwitches') return positive ? '#EF4444' : '#22C55E'
  return positive ? '#22C55E' : '#EF4444'
}

const METRIC_DEFS = [
  { key: 'activeTime', label: 'Active', tooltip: 'Total time with activity detected', format: formatMinutes, color: 'var(--to-brand)' },
  { key: 'workMinutes', label: 'Work Time', tooltip: 'Total time on work categories', format: formatMinutes, color: '#0d7377' },
  { key: 'deepWork', label: 'Deep Work', tooltip: 'Time in deep focus on complex tasks', format: formatMinutes, color: SEMANTIC_COLORS.deep },
  { key: 'avgFocus', label: 'Focus', tooltip: 'Average focus quality', format: (v: number) => Math.round(v * 100) + '%', color: null },
  { key: 'longestFocus', label: 'Best Streak', tooltip: 'Longest unbroken focus streak', format: formatMinutes, color: '#7c3aed' },
  { key: 'contextSwitches', label: 'Switches', tooltip: 'Number of depth transitions', format: (v: number) => v.toString(), color: '#d97706' },
] as const
</script>

<template>
  <NSpin :show="loading">
    <NSpace vertical :size="20">
      <div class="status-banner">
        <div class="status-dot" :class="isActive ? 'active' : 'inactive'" />
        <NText style="font-weight: 500">Daemon {{ isActive ? 'active' : 'inactive' }}</NText>
        <NText depth="3" style="font-size: 13px">{{ lastEventText }}</NText>
        <NText depth="3" style="font-size: 13px">{{ activityStore.status?.events_today ?? 0 }} events today</NText>
      </div>

      <div class="period-controls">
        <NButtonGroup size="small">
          <NButton :type="periodMode === 'day' ? 'primary' : 'default'" @click="setPeriod('day')">Day</NButton>
          <NButton :type="periodMode === 'week' ? 'primary' : 'default'" @click="setPeriod('week')">Week</NButton>
          <NButton :type="periodMode === 'month' ? 'primary' : 'default'" @click="setPeriod('month')">Month</NButton>
        </NButtonGroup>
        <div class="date-nav">
          <NButton text @click="navigateDate(-1)" style="font-size: 18px">&lsaquo;</NButton>
          <NText strong style="min-width: 140px; text-align: center">{{ periodLabel }}</NText>
          <NButton text @click="navigateDate(1)" style="font-size: 18px">&rsaquo;</NButton>
        </div>
        <NButton size="small" secondary @click="goToday">Today</NButton>
        <NSelect
          v-if="periodMode !== 'day'"
          v-model:value="bucketMinutes"
          :options="BUCKET_OPTIONS[periodMode]"
          size="small"
          style="width: 110px"
        />
      </div>

      <div v-if="narrative" class="narrative-card">
        <NText>{{ narrative }}</NText>
      </div>

      <div class="curve-heatmap-row">
        <NCard size="small" class="curve-card">
          <template #header>
            <div style="display: flex; align-items: baseline; gap: 12px">
              <span style="font-weight: 600">Productivity</span>
              <span
                v-if="curveScores.productivity !== null"
                style="font-size: 28px; font-weight: 700; color: var(--to-brand)"
              >{{ Math.round(curveScores.productivity!) }}</span>
              <span v-if="curveScores.productivity !== null" style="font-size: 13px; opacity: 0.5">/ 100</span>
              <NTooltip v-if="curveScores.performance !== null">
                <template #trigger>
                  <span
                    style="font-size: 16px; font-weight: 600; color: #7c3aed; margin-left: 8px"
                  >{{ Math.round(curveScores.performance!) }}</span>
                </template>
                Performance (work-only)
              </NTooltip>
              <span v-if="curveScores.workMinutes" style="font-size: 13px; opacity: 0.5; margin-left: auto">
                {{ formatMinutes(curveScores.workMinutes) }} work
              </span>
            </div>
          </template>
          <div v-if="periodMode === 'day' && dayCurve && dayCurve.points.length">
            <ProductivityCurve
              :key="'day-' + selectedDate"
              :points="dayCurve.points"
              :entries="entries"
            />
          </div>
          <div v-else-if="periodMode !== 'day' && aggregatedCurve && aggregatedCurve.buckets.length">
            <ProductivityCurve
              :key="periodMode + '-' + dateRange.start + '-' + bucketMinutes"
              :buckets="aggregatedCurve.buckets"
              :bucket-minutes="aggregatedCurve.bucket_minutes"
              :entries="entries"
            />
          </div>
          <NEmpty v-else description="No data for this period" />
        </NCard>
        <div v-if="heatmapGrid" class="heatmap-panel">
          <table class="heatmap-table">
            <thead>
              <tr>
                <th />
                <th v-for="col in heatmapGrid.columns" :key="col">{{ col }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in heatmapGrid.cells" :key="ri">
                <td class="heatmap-row-label">{{ heatmapGrid.rows[ri] }}</td>
                <td v-for="(score, ci) in row" :key="ci">
                  <NTooltip>
                    <template #trigger>
                      <div
                        class="heatmap-cell"
                        :style="{ backgroundColor: heatmapColor(score) }"
                      />
                    </template>
                    {{ heatmapGrid.labels.get(`${ri}-${ci}`) }}: {{ score !== null ? Math.round(score) : 'no data' }}
                  </NTooltip>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <NCard v-if="metrics" size="small">
        <div class="metrics-grid">
          <template v-for="def in METRIC_DEFS" :key="def.key">
            <NTooltip v-if="(metrics as any)[def.key] !== null && (metrics as any)[def.key] !== undefined">
              <template #trigger>
                <div class="metric-item">
                  <div class="metric-label">{{ def.label }}</div>
                  <div
                    class="metric-value"
                    :style="{ color: def.key === 'avgFocus' ? focusScoreColor(metrics.avgFocus) : (def.color || 'var(--to-text-primary)') }"
                  >{{ def.format((metrics as any)[def.key]) }}</div>
                  <div
                    v-if="prevMetrics && (prevMetrics as any)[def.key] !== null && (prevMetrics as any)[def.key] !== undefined"
                    class="metric-delta"
                    :style="{ color: deltaColor(def.key, (metrics as any)[def.key] - (prevMetrics as any)[def.key]) }"
                  >{{ formatDelta(def.key, (metrics as any)[def.key], (prevMetrics as any)[def.key]) }}</div>
                </div>
              </template>
              {{ def.tooltip }}
            </NTooltip>
          </template>
        </div>
      </NCard>

      <div class="categories-timeline-row">
        <NCard v-if="categoryBreakdown.length" size="small" class="half-card">
          <template #header><span style="font-weight: 600">Categories</span></template>
          <CategoryBreakdownChart :items="categoryBreakdown" />
        </NCard>

        <NCard title="Timeline" size="small" class="half-card">
          <template #header-extra>
            <NButton text type="primary" size="small" @click="router.push({ name: 'timeline' })">
              View Calendar
            </NButton>
          </template>
          <NEmpty v-if="!entries.length" description="No timeline entries" />
          <template v-else>
            <NList :show-divider="false" style="margin: -4px 0">
              <NListItem v-for="entry in displayedEntries" :key="entry.id" class="list-item-compact">
                <NSpace align="center" :size="8">
                  <div v-if="entry.color" class="color-dot" :style="{ backgroundColor: entry.color }" />
                  <NText strong class="item-label">{{ entry.label }}</NText>
                  <NText depth="3" class="item-meta">
                    {{ periodMode === 'day'
                      ? `${format(new Date(entry.start_time), 'HH:mm')}–${format(new Date(entry.end_time), 'HH:mm')}`
                      : `${format(new Date(entry.start_time), 'EEE HH:mm')}–${format(new Date(entry.end_time), 'HH:mm')}`
                    }}
                  </NText>
                  <NText v-if="entry.category" depth="3" class="item-meta">· {{ entry.category }}</NText>
                </NSpace>
              </NListItem>
            </NList>
            <NButton
              v-if="entries.length > 8"
              text
              type="primary"
              size="small"
              style="margin-top: 4px"
              @click="showAllEntries = !showAllEntries"
            >
              {{ showAllEntries ? 'Show less' : `Show all (${entries.length})` }}
            </NButton>
          </template>
        </NCard>
      </div>
    </NSpace>
  </NSpin>
</template>

<style scoped>
.period-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.date-nav {
  display: flex;
  align-items: center;
  gap: 4px;
}

.narrative-card {
  padding: 12px 16px;
  border-radius: 8px;
  background: var(--to-card);
  border-left: 3px solid var(--to-brand);
  font-size: 14px;
  line-height: 1.5;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.metric-item {
  text-align: center;
  cursor: default;
}

.metric-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  opacity: 0.5;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 20px;
  font-weight: 700;
}

.metric-delta {
  font-size: 11px;
  font-weight: 600;
  margin-top: 2px;
}

.curve-heatmap-row {
  display: flex;
  gap: 16px;
  align-items: stretch;
}

.curve-card {
  flex: 1;
  min-width: 0;
}

.heatmap-panel {
  flex-shrink: 0;
  padding: 12px;
  border-radius: 8px;
  background: var(--to-card);
  display: flex;
  align-items: center;
}

.heatmap-table {
  border-spacing: 3px;
  border-collapse: separate;
}

.heatmap-table th {
  font-size: 11px;
  font-weight: 500;
  opacity: 0.4;
  text-transform: uppercase;
  padding: 0 0 4px;
  text-align: center;
}

.heatmap-table th:first-child {
  width: 0;
}

.heatmap-row-label {
  font-size: 10px;
  opacity: 0.4;
  padding-right: 6px;
  white-space: nowrap;
  text-align: right;
}

.heatmap-cell {
  width: 28px;
  height: 28px;
  border-radius: 4px;
}


.categories-timeline-row {
  display: flex;
  gap: 16px;
  align-items: stretch;
}

.half-card {
  flex: 1;
  min-width: 0;
}

@media (max-width: 768px) {
  .categories-timeline-row {
    flex-direction: column;
  }
}

@media (max-width: 480px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
