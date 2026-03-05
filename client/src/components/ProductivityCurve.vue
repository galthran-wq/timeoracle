<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  TimeScale,
  Filler,
  Tooltip,
} from 'chart.js'
import 'chartjs-adapter-date-fns'
import type { ProductivityPoint, AggregatedBucket } from '@/types/productivityCurve'
import type { TimelineEntry } from '@/types/timeline'

Chart.register(LineController, LineElement, PointElement, LinearScale, TimeScale, Filler, Tooltip)

const props = withDefaults(defineProps<{
  points?: ProductivityPoint[]
  buckets?: AggregatedBucket[]
  bucketMinutes?: number
  entries: TimelineEntry[]
}>(), {
  points: undefined,
  buckets: undefined,
  bucketMinutes: 10,
})

const canvasEl = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null

function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

function findEntry(timestamp: number): TimelineEntry | null {
  for (const e of props.entries) {
    const s = new Date(e.start_time).getTime()
    const end = new Date(e.end_time).getTime()
    if (timestamp >= s && timestamp < end) return e
  }
  return null
}

function buildPointData() {
  const data: { x: number; y: number | null; color: string; entryLabel: string | null; entryDescription: string | null; category: string | null; depth: string | null; isWork: boolean }[] = []
  if (!props.points) return data

  const TEN_MIN = 10 * 60 * 1000
  const GAP_THRESHOLD = 15 * 60 * 1000

  for (let i = 0; i < props.points.length; i++) {
    const p = props.points[i]
    const ts = new Date(p.interval_start).getTime()

    if (i > 0) {
      const prevTs = new Date(props.points[i - 1].interval_start).getTime()
      if (ts - prevTs > GAP_THRESHOLD) {
        data.push({ x: prevTs + TEN_MIN, y: null, color: '', entryLabel: null, entryDescription: null, category: null, depth: null, isWork: false })
      }
    }

    const entry = findEntry(ts)
    const color = p.color || '#6B7280'

    data.push({
      x: ts,
      y: p.productivity_score,
      color,
      entryLabel: entry?.label ?? null,
      entryDescription: entry?.description ?? null,
      category: p.category,
      depth: p.depth,
      isWork: p.is_work,
    })
  }

  return data
}

function buildLineChart(data: ReturnType<typeof buildPointData>) {
  if (!canvasEl.value) return

  chart = new Chart(canvasEl.value, {
    type: 'line',
    data: {
      datasets: [
        {
          data: data.map((d) => ({ x: d.x, y: d.y })),
          fill: 'origin',
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 0,
          pointHitRadius: 12,
          pointHoverRadius: 5,
          spanGaps: false,
          segment: {
            borderColor: (ctx: any) => data[ctx.p0DataIndex]?.color || '#6B7280',
            backgroundColor: (ctx: any) => {
              const d = data[ctx.p0DataIndex]
              if (!d?.color) return 'rgba(107,114,128,0.15)'
              return hexToRgba(d.color, d.isWork ? 0.25 : 0.10)
            },
          },
          pointBackgroundColor: (ctx: any) => data[ctx.dataIndex]?.color || '#6B7280',
          pointBorderColor: (ctx: any) => data[ctx.dataIndex]?.color || '#6B7280',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'nearest', axis: 'x', intersect: false },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'hour', displayFormats: { hour: 'HH:mm' }, tooltipFormat: 'HH:mm' },
          grid: { color: 'rgba(150,150,150,0.08)' },
          ticks: { color: 'rgba(150,150,150,0.6)', font: { size: 11 } },
        },
        y: {
          min: 0,
          max: 100,
          grid: { color: 'rgba(150,150,150,0.08)' },
          ticks: { color: 'rgba(150,150,150,0.6)', font: { size: 11 }, stepSize: 25 },
        },
      },
      plugins: {
        tooltip: {
          callbacks: {
            title: (items: any[]) => {
              if (!items.length) return ''
              const d = data[items[0].dataIndex]
              if (!d) return ''
              const time = new Date(d.x).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              return d.entryLabel ? `${time} \u2014 ${d.entryLabel}` : time
            },
            label: (item: any) => {
              const d = data[item.dataIndex]
              if (!d || d.y == null) return ''
              const parts = [`Score: ${Math.round(d.y)}`]
              if (d.category) parts.push(d.category)
              if (d.depth) parts.push(d.depth)
              return parts.join('  \u00b7  ')
            },
            afterBody: (items: any[]) => {
              if (!items.length) return ''
              const d = data[items[0].dataIndex]
              if (!d?.entryDescription) return ''
              const words = d.entryDescription.split(' ')
              const lines: string[] = []
              let line = ''
              for (const w of words) {
                if (line && (line + ' ' + w).length > 50) {
                  lines.push(line)
                  line = w
                } else {
                  line = line ? line + ' ' + w : w
                }
              }
              if (line) lines.push(line)
              return ['', ...lines]
            },
          },
          backgroundColor: 'rgba(20,20,20,0.9)',
          titleFont: { weight: 'bold' as const, size: 13 },
          bodyFont: { size: 12 },
          padding: 10,
          cornerRadius: 6,
          maxWidth: 350,
        },
      },
    },
  })
}

function buildBucketLineChart() {
  if (!canvasEl.value || !props.buckets?.length) return

  const data = props.buckets.map((b) => ({
    x: new Date(b.bucket_start).getTime(),
    y: b.avg_productivity_score,
    color: b.dominant_color || '#6B7280',
    category: b.dominant_category,
    performance: b.avg_performance_score,
    pointCount: b.point_count,
    workCount: b.work_point_count,
  }))

  const timeUnit = props.bucketMinutes >= 1440 ? 'day' as const : props.bucketMinutes >= 360 ? 'day' as const : 'hour' as const
  const displayFormat = props.bucketMinutes >= 1440 ? 'MMM d' : 'MMM d HH:mm'

  chart = new Chart(canvasEl.value, {
    type: 'line',
    data: {
      datasets: [
        {
          data: data.map((d) => ({ x: d.x, y: d.y })),
          fill: 'origin',
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 3,
          pointHitRadius: 12,
          pointHoverRadius: 6,
          spanGaps: false,
          segment: {
            borderColor: (ctx: any) => data[ctx.p0DataIndex]?.color || '#6B7280',
            backgroundColor: (ctx: any) => {
              const d = data[ctx.p0DataIndex]
              return d?.color ? hexToRgba(d.color, 0.15) : 'rgba(107,114,128,0.15)'
            },
          },
          pointBackgroundColor: (ctx: any) => data[ctx.dataIndex]?.color || '#6B7280',
          pointBorderColor: (ctx: any) => data[ctx.dataIndex]?.color || '#6B7280',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'nearest', axis: 'x', intersect: false },
      scales: {
        x: {
          type: 'time',
          time: { unit: timeUnit, displayFormats: { hour: 'HH:mm', day: displayFormat }, tooltipFormat: displayFormat },
          grid: { color: 'rgba(150,150,150,0.08)' },
          ticks: { color: 'rgba(150,150,150,0.6)', font: { size: 11 } },
        },
        y: {
          min: 0,
          max: 100,
          grid: { color: 'rgba(150,150,150,0.08)' },
          ticks: { color: 'rgba(150,150,150,0.6)', font: { size: 11 }, stepSize: 25 },
        },
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: (item: any) => {
              const d = data[item.dataIndex]
              if (!d || d.y == null) return ''
              const parts = [`Score: ${Math.round(d.y)}`]
              if (d.category) parts.push(d.category)
              return parts.join('  \u00b7  ')
            },
            afterBody: (items: any[]) => {
              if (!items.length) return ''
              const d = data[items[0].dataIndex]
              if (!d) return ''
              const lines: string[] = []
              if (d.performance !== null) lines.push(`Performance: ${Math.round(d.performance)}`)
              lines.push(`${d.pointCount} points (${d.workCount} work)`)
              return lines
            },
          },
          backgroundColor: 'rgba(20,20,20,0.9)',
          titleFont: { weight: 'bold' as const, size: 13 },
          bodyFont: { size: 12 },
          padding: 10,
          cornerRadius: 6,
          maxWidth: 350,
        },
      },
    },
  })
}

function buildChart() {
  if (chart) {
    chart.destroy()
    chart = null
  }

  if (props.points?.length) {
    buildLineChart(buildPointData())
  } else if (props.buckets?.length) {
    buildBucketLineChart()
  }
}

watch(
  () => [props.points, props.buckets, props.entries, props.bucketMinutes],
  () => nextTick(buildChart),
  { deep: true },
)

onMounted(() => nextTick(buildChart))

onUnmounted(() => {
  if (chart) {
    chart.destroy()
    chart = null
  }
})
</script>

<template>
  <div class="productivity-curve">
    <canvas ref="canvasEl" />
  </div>
</template>

<style scoped>
.productivity-curve {
  width: 100%;
  height: 220px;
  position: relative;
}
</style>
