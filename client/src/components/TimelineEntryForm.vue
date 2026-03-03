<script setup lang="ts">
import { ref, watch, computed, nextTick, onUnmounted } from 'vue'
import {
  NInput,
  NTimePicker,
  NButton,
  NSpace,
  NPopconfirm,
  NSelect,
  NText,
  NTooltip,
} from 'naive-ui'
import { set, addDays } from 'date-fns'
import { formatISO } from 'date-fns'
import type { TimelineEntry } from '@/types/timeline'
import { DEFAULT_ENTRY_COLOR } from '@/constants/palette'
import type { CategoryConfig } from '@/constants/categories'
import { getDefaultCategories } from '@/api/settings'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  show: boolean
  entry: TimelineEntry | null
  date: string
  defaultStartTime?: string
  clickPos?: { x: number; y: number }
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'save', data: { label: string; start_time: string; end_time: string; date: string; category: string; color: string; description: string }): void
  (e: 'delete', id: string): void
}>()

const isEdit = computed(() => !!props.entry)
const expanded = ref(false)

const label = ref('')
const startTime = ref<number | null>(null)
const endTime = ref<number | null>(null)
const category = ref('')
const color = ref(DEFAULT_ENTRY_COLOR)
const description = ref('')

const auth = useAuthStore()
const defaultCategories = ref<Record<string, CategoryConfig>>({})
const categories = computed(() => auth.user?.session_config?.categories ?? defaultCategories.value)
const categoryOptions = computed(() =>
  Object.entries(categories.value)
    .filter(([, cfg]) => !cfg.deprecated)
    .map(([name]) => ({ label: name, value: name })),
)

getDefaultCategories().then((d) => { defaultCategories.value = d }).catch(() => {})

function onCategoryChange(value: string | null) {
  category.value = value ?? ''
  if (value && categories.value[value]) {
    color.value = categories.value[value].color
  }
}

const panelRef = ref<HTMLElement | null>(null)
const panelStyle = ref<Record<string, string>>({})

function computePosition() {
  const pos = props.clickPos
  if (!pos) {
    panelStyle.value = { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }
    return
  }

  const panelW = 380
  const panelH = 420
  const margin = 12
  const vw = window.innerWidth
  const vh = window.innerHeight

  let x = pos.x + margin
  let y = pos.y - panelH / 3

  if (x + panelW > vw - margin) x = pos.x - panelW - margin
  if (x < margin) x = margin
  if (y + panelH > vh - margin) y = vh - margin - panelH
  if (y < margin) y = margin

  panelStyle.value = { top: y + 'px', left: x + 'px' }
}

watch(
  () => props.show,
  async (show) => {
    if (!show) {
      expanded.value = false
      return
    }
    if (props.entry) {
      label.value = props.entry.label
      startTime.value = new Date(props.entry.start_time).getTime()
      endTime.value = new Date(props.entry.end_time).getTime()
      category.value = props.entry.category ?? ''
      color.value = props.entry.color ?? DEFAULT_ENTRY_COLOR
      description.value = props.entry.description ?? ''
      expanded.value = !!(props.entry.category || props.entry.description)
    } else {
      label.value = ''
      category.value = ''
      color.value = DEFAULT_ENTRY_COLOR
      description.value = ''
      if (props.defaultStartTime) {
        const dt = new Date(props.defaultStartTime)
        startTime.value = dt.getTime()
        endTime.value = new Date(dt.getTime() + 60 * 60 * 1000).getTime()
      } else {
        const now = new Date()
        startTime.value = now.getTime()
        endTime.value = new Date(now.getTime() + 60 * 60 * 1000).getTime()
      }
    }
    computePosition()
    await nextTick()
    panelRef.value?.querySelector<HTMLInputElement>('input')?.focus()
  },
)

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') close()
}

watch(() => props.show, (show) => {
  if (show) {
    window.addEventListener('keydown', handleKeydown)
  } else {
    window.removeEventListener('keydown', handleKeydown)
  }
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

function hourInTimezone(dt: Date, timezone: string): number {
  const formatter = new Intl.DateTimeFormat('en-US', { timeZone: timezone, hour: '2-digit', hour12: false })
  const parts = formatter.formatToParts(dt)
  const hourValue = parts.find((p) => p.type === 'hour')?.value
  const hour = Number(hourValue === '24' ? '0' : hourValue)
  return Number.isNaN(hour) ? dt.getHours() : hour
}

function buildISOFromTimePicker(timeMs: number): string {
  const d = new Date(timeMs)
  const dateParts = props.date.split('-').map(Number)
  let merged = set(d, { year: dateParts[0], month: dateParts[1] - 1, date: dateParts[2] })
  const dayStartHour = auth.user?.session_config?.day_start_hour ?? 0
  const timezone = auth.user?.session_config?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone
  const hour = hourInTimezone(merged, timezone)
  if (dayStartHour > 0 && hour < dayStartHour) {
    merged = addDays(merged, 1)
  }
  return formatISO(merged)
}

function handleSave() {
  if (!label.value || startTime.value === null || endTime.value === null) return
  emit('save', {
    label: label.value,
    start_time: buildISOFromTimePicker(startTime.value),
    end_time: buildISOFromTimePicker(endTime.value),
    date: props.date,
    category: category.value,
    color: color.value,
    description: description.value,
  })
}

function handleDelete() {
  if (props.entry) emit('delete', props.entry.id)
}

function close() {
  emit('update:show', false)
}
</script>

<template>
  <Teleport to="body">
    <Transition name="entry-panel">
      <div v-if="show" class="entry-panel-overlay" @mousedown.self="close">
        <div ref="panelRef" class="entry-panel" :style="panelStyle">
          <form @submit.prevent="handleSave">
            <NInput
              v-model:value="label"
              placeholder="What were you doing?"
              size="large"
              :style="{ marginBottom: '12px' }"
            />

            <NSpace align="center" :size="8" style="margin-bottom: 12px">
              <NSpace :size="4" align="center">
                <NTimePicker v-model:value="startTime" format="HH:mm" style="width: 110px" size="small" />
                <NText depth="3">–</NText>
                <NTimePicker v-model:value="endTime" format="HH:mm" style="width: 110px" size="small" />
              </NSpace>
            </NSpace>

            <div style="margin-bottom: 12px">
              <NTooltip>
                <template #trigger>
                  <NSelect
                    :value="category || null"
                    :options="categoryOptions"
                    placeholder="Category"
                    size="small"
                    filterable
                    clearable
                    @update:value="onCategoryChange"
                  />
                </template>
                Manage categories in Settings
              </NTooltip>
            </div>

            <template v-if="expanded || isEdit">
              <NInput
                v-model:value="description"
                type="textarea"
                :autosize="{ minRows: 2, maxRows: 10 }"
                placeholder="Notes (optional)"
                size="small"
                style="margin-bottom: 12px"
              />
            </template>

            <NSpace justify="space-between" align="center">
              <NSpace :size="8">
                <NButton
                  v-if="!expanded && !isEdit"
                  text
                  size="small"
                  @click="expanded = true"
                >
                  More options
                </NButton>
                <NPopconfirm v-if="isEdit" @positive-click="handleDelete">
                  <template #trigger>
                    <NButton text type="error" size="small">Delete</NButton>
                  </template>
                  Delete this entry?
                </NPopconfirm>
              </NSpace>
              <NSpace :size="8">
                <NButton size="small" @click="close">Cancel</NButton>
                <NButton type="primary" size="small" attr-type="submit" :disabled="!label">Save</NButton>
              </NSpace>
            </NSpace>
          </form>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
