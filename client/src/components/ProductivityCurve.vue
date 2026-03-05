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
import type { ProductivityPoint } from '@/types/productivityCurve'
import type { TimelineEntry } from '@/types/timeline'

Chart.register(LineController, LineElement, PointElement, LinearScale, TimeScale, Filler, Tooltip)

const props = defineProps<{
  points: ProductivityPoint[]
  entries: TimelineEntry[]
}>()

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

function buildData() {
  const data: { x: number; y: number | null; color: string; entryLabel: string | null; entryDescription: string | null; category: string | null; depth: string | null; isWork: boolean }[] = []

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

function buildChart() {
  if (!canvasEl.value || !props.points.length) return
  if (chart) {
    chart.destroy()
    chart = null
  }

  const data = buildData()

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
            borderColor: (ctx: any) => {
              const i = ctx.p0DataIndex
              return data[i]?.color || '#6B7280'
            },
            backgroundColor: (ctx: any) => {
              const i = ctx.p0DataIndex
              const d = data[i]
              if (!d?.color) return 'rgba(107,114,128,0.15)'
              const alpha = d.isWork ? 0.25 : 0.10
              return hexToRgba(d.color, alpha)
            },
          },
          pointBackgroundColor: (ctx: any) => {
            const i = ctx.dataIndex
            return data[i]?.color || '#6B7280'
          },
          pointBorderColor: (ctx: any) => {
            const i = ctx.dataIndex
            return data[i]?.color || '#6B7280'
          },
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'nearest',
        axis: 'x',
        intersect: false,
      },
      scales: {
        x: {
          type: 'time',
          time: {
            unit: 'hour',
            displayFormats: { hour: 'HH:mm' },
            tooltipFormat: 'HH:mm',
          },
          grid: { color: 'rgba(150,150,150,0.08)' },
          ticks: { color: 'rgba(150,150,150,0.6)', font: { size: 11 } },
        },
        y: {
          min: 0,
          max: 100,
          grid: { color: 'rgba(150,150,150,0.08)' },
          ticks: {
            color: 'rgba(150,150,150,0.6)',
            font: { size: 11 },
            stepSize: 25,
          },
        },
      },
      plugins: {
        tooltip: {
          callbacks: {
            title: (items: any[]) => {
              if (!items.length) return ''
              const i = items[0].dataIndex
              const d = data[i]
              if (!d) return ''
              const time = new Date(d.x).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              return d.entryLabel ? `${time} — ${d.entryLabel}` : time
            },
            label: (item: any) => {
              const i = item.dataIndex
              const d = data[i]
              if (!d || d.y == null) return ''
              const parts = [`Score: ${Math.round(d.y)}`]
              if (d.category) parts.push(d.category)
              if (d.depth) parts.push(d.depth)
              return parts.join('  ·  ')
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
          footerFont: { size: 11, weight: 'normal' as const },
          padding: 10,
          cornerRadius: 6,
          maxWidth: 350,
        },
      },
    },
  })
}

watch(
  () => [props.points, props.entries],
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
