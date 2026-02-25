<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { NSpace, NButton, NSpin, NText, useMessage } from 'naive-ui'
import { ScheduleXCalendar } from '@schedule-x/vue'
import { createCalendar, viewDay, viewWeek } from '@schedule-x/calendar'
import { createDragAndDropPlugin } from '@schedule-x/drag-and-drop'
import { createResizePlugin } from '@schedule-x/resize'
import { formatISO } from 'date-fns'
import { useTimelineStore } from '@/stores/timeline'
import { useActivityStore } from '@/stores/activity'
import { ApiError } from '@/api/client'
import { createSessionLinesPlugin } from '@/plugins/sessionLines'
import TimelineEntryForm from '@/components/TimelineEntryForm.vue'
import type { TimelineEntry } from '@/types/timeline'

import '@schedule-x/theme-default/dist/index.css'

const SESSION_PALETTE = [
  { main: '#6366F1', container: '#E0E7FF', onContainer: '#312E81' }, // indigo
  { main: '#14B8A6', container: '#CCFBF1', onContainer: '#134E4A' }, // teal
  { main: '#F59E0B', container: '#FEF3C7', onContainer: '#78350F' }, // amber
  { main: '#EC4899', container: '#FCE7F3', onContainer: '#831843' }, // pink
  { main: '#8B5CF6', container: '#EDE9FE', onContainer: '#4C1D95' }, // violet
  { main: '#10B981', container: '#D1FAE5', onContainer: '#064E3B' }, // emerald
  { main: '#F97316', container: '#FFEDD5', onContainer: '#7C2D12' }, // orange
  { main: '#06B6D4', container: '#CFFAFE', onContainer: '#155E75' }, // cyan
]

const message = useMessage()
const timelineStore = useTimelineStore()
const activityStore = useActivityStore()

const showForm = ref(false)
const editingEntry = ref<TimelineEntry | null>(null)
const clickedTime = ref<string | undefined>(undefined)
const showSessions = ref(localStorage.getItem('showSessions') !== 'false')

const dragAndDrop = createDragAndDropPlugin()
const eventResize = createResizePlugin()
const sessionLines = createSessionLinesPlugin(SESSION_PALETTE)

const tz = Temporal.Now.timeZoneId()

function isoToZoned(iso: string): Temporal.ZonedDateTime {
  const d = new Date(iso)
  return Temporal.ZonedDateTime.from({
    year: d.getFullYear(),
    month: d.getMonth() + 1,
    day: d.getDate(),
    hour: d.getHours(),
    minute: d.getMinutes(),
    timeZone: tz,
  })
}

function entryToEvent(e: TimelineEntry) {
  return {
    id: e.id,
    title: e.category ? `${e.label} (${e.category})` : e.label,
    start: isoToZoned(e.start_time),
    end: isoToZoned(e.end_time),
    calendarId: 'timeline',
  }
}

function toggleSessions() {
  showSessions.value = !showSessions.value
  localStorage.setItem('showSessions', String(showSessions.value))
  syncEvents()
}

const calendar = createCalendar({
  views: [viewDay, viewWeek],
  defaultView: viewDay.name,
  selectedDate: Temporal.PlainDate.from(timelineStore.selectedDate),
  events: [],
  plugins: [dragAndDrop, eventResize, sessionLines],
  calendars: {
    timeline: {
      colorName: 'timeline',
      lightColors: { main: '#3B82F6', container: '#DBEAFE', onContainer: '#1E3A5F' },
      darkColors: { main: '#60A5FA', container: '#1E3A5F', onContainer: '#DBEAFE' },
    },
  },
  callbacks: {
    onEventClick(event) {
      const entry = timelineStore.entries.find((e) => e.id === String(event.id))
      if (entry) {
        editingEntry.value = entry
        clickedTime.value = undefined
        showForm.value = true
      }
    },
    onClickDateTime(dateTime) {
      editingEntry.value = null
      clickedTime.value = new Date(dateTime.epochMilliseconds).toISOString()
      showForm.value = true
    },
    onSelectedDateUpdate(date) {
      timelineStore.selectedDate = date.toString()
    },
    async onEventUpdate(updatedEvent) {
      try {
        const start = updatedEvent.start as Temporal.ZonedDateTime
        const end = updatedEvent.end as Temporal.ZonedDateTime
        await timelineStore.updateEntry(String(updatedEvent.id), {
          start_time: formatISO(new Date(start.epochMilliseconds)),
          end_time: formatISO(new Date(end.epochMilliseconds)),
        })
      } catch (e) {
        message.error(e instanceof ApiError ? e.message : 'Failed to update entry')
        await timelineStore.fetchEntries()
      }
    },
  },
})

const sessionApps = computed(() => {
  if (!showSessions.value) return []
  const map = new Map<string, number>()
  let idx = 0
  for (const s of activityStore.sessions) {
    if (!map.has(s.app_name)) map.set(s.app_name, idx++)
  }
  return [...map.entries()].map(([app, i]) => [
    app,
    SESSION_PALETTE[i % SESSION_PALETTE.length].main,
  ] as [string, string])
})

function syncEvents() {
  try {
    calendar.events.set(timelineStore.entries.map(entryToEvent))
  } catch { }

  try {
    ;(calendar as any).sessionLines.setSessions(
      showSessions.value ? activityStore.sessions : []
    )
  } catch { }
}

watch(() => timelineStore.entries, syncEvents, { deep: true })
watch(() => activityStore.sessions, syncEvents, { deep: true })

watch(
  () => timelineStore.selectedDate,
  (date) => activityStore.fetchSessions(date),
)

onMounted(async () => {
  await Promise.all([
    timelineStore.fetchEntries(),
    activityStore.fetchSessions(timelineStore.selectedDate),
  ])
})

async function handleSave(data: {
  label: string
  start_time: string
  end_time: string
  date: string
  category: string
  color: string
  description: string
}) {
  try {
    const payload = {
      ...data,
      category: data.category || null,
      color: data.color || null,
      description: data.description || null,
    }
    if (editingEntry.value) {
      const { date: _, ...updatePayload } = payload
      await timelineStore.updateEntry(editingEntry.value.id, updatePayload)
      message.success('Entry updated')
    } else {
      await timelineStore.createEntry(payload)
      message.success('Entry created')
    }
    showForm.value = false
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : 'Failed to save entry')
  }
}

async function handleDelete(id: string) {
  try {
    await timelineStore.deleteEntry(id)
    message.success('Entry deleted')
    showForm.value = false
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : 'Failed to delete entry')
  }
}

function openCreate() {
  editingEntry.value = null
  clickedTime.value = undefined
  showForm.value = true
}
</script>

<template>
  <div style="height: 100%; display: flex; flex-direction: column">
    <NSpace justify="end" align="center" style="margin-bottom: 12px">
      <NSpace v-if="showSessions && sessionApps.length" :size="8" align="center">
        <template v-for="[app, color] in sessionApps" :key="app">
          <NSpace :size="4" align="center">
            <div :style="{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: color }" />
            <NText depth="3" style="font-size: 12px">{{ app }}</NText>
          </NSpace>
        </template>
      </NSpace>
      <NButton
        :type="showSessions ? 'default' : 'tertiary'"
        @click="toggleSessions"
      >
        {{ showSessions ? 'Hide Sessions' : 'Show Sessions' }}
      </NButton>
      <NButton type="primary" @click="openCreate">+ New Entry</NButton>
    </NSpace>

    <NSpin :show="timelineStore.loading" style="flex: 1; min-height: 0">
      <div style="height: 100%; min-height: 600px">
        <ScheduleXCalendar :calendar-app="calendar" />
      </div>
    </NSpin>

    <TimelineEntryForm
      v-model:show="showForm"
      :entry="editingEntry"
      :date="timelineStore.selectedDate"
      :default-start-time="clickedTime"
      @save="handleSave"
      @delete="handleDelete"
    />
  </div>
</template>

<style>
</style>