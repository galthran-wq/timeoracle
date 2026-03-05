<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import {
  Chart,
  PolarAreaController,
  ArcElement,
  RadialLinearScale,
  Tooltip,
} from 'chart.js'

Chart.register(PolarAreaController, ArcElement, RadialLinearScale, Tooltip)

interface CategoryItem {
  category: string
  minutes: number
  avgScore: number | null
  color: string
}

const props = defineProps<{ items: CategoryItem[] }>()

const canvasEl = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null

function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

function formatMinutes(mins: number): string {
  const rounded = Math.round(mins)
  if (rounded < 60) return `${rounded}m`
  const h = Math.floor(rounded / 60)
  const m = rounded % 60
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

function buildChart() {
  if (chart) {
    chart.destroy()
    chart = null
  }
  if (!canvasEl.value || !props.items.length) return

  const items = props.items

  chart = new Chart(canvasEl.value, {
    type: 'polarArea',
    data: {
      labels: items.map((d) => d.category),
      datasets: [
        {
          data: items.map((d) => d.avgScore ?? 50),
          backgroundColor: items.map((d) => hexToRgba(d.color, 0.6)),
          borderColor: items.map((d) => hexToRgba(d.color, 0.9)),
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      scales: {
        r: {
          min: 0,
          max: 100,
          ticks: {
            display: false,
          },
          grid: { color: 'rgba(150,150,150,0.08)' },
          pointLabels: { display: false },
        },
      },
      plugins: {
        tooltip: {
          callbacks: {
            title: (ctx: any) => {
              if (!ctx.length) return ''
              return items[ctx[0].dataIndex].category
            },
            label: (ctx: any) => {
              const d = items[ctx.dataIndex]
              const parts = [formatMinutes(d.minutes)]
              if (d.avgScore !== null) parts.push(`Score: ${Math.round(d.avgScore)}`)
              return parts.join('  \u00b7  ')
            },
          },
          backgroundColor: 'rgba(20,20,20,0.9)',
          titleFont: { weight: 'bold' as const, size: 13 },
          bodyFont: { size: 12 },
          padding: 10,
          cornerRadius: 6,
        },
      },
    },
  })
}

watch(() => props.items, () => nextTick(buildChart), { deep: true })
onMounted(() => nextTick(buildChart))
onUnmounted(() => {
  if (chart) {
    chart.destroy()
    chart = null
  }
})
</script>

<template>
  <div>
    <div class="category-polar-chart">
      <canvas ref="canvasEl" />
    </div>
    <div class="polar-legend">
      <span v-for="item in items" :key="item.category" class="polar-legend-item">
        <span class="polar-legend-dot" :style="{ backgroundColor: item.color }" />
        <span class="polar-legend-name">{{ item.category }}</span>
        <span class="polar-legend-time">{{ formatMinutes(item.minutes) }}</span>
        <span v-if="item.avgScore !== null" class="polar-legend-score">{{ Math.round(item.avgScore) }}</span>
      </span>
    </div>
  </div>
</template>

<style scoped>
.category-polar-chart {
  width: 100%;
  max-width: 220px;
  margin: 0 auto;
}

.polar-legend {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 8px;
  font-size: 12px;
}

.polar-legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.polar-legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.polar-legend-name {
  opacity: 0.7;
  flex: 1;
}

.polar-legend-time {
  font-weight: 600;
  opacity: 0.6;
}

.polar-legend-score {
  font-weight: 700;
  min-width: 24px;
  text-align: right;
}
</style>
