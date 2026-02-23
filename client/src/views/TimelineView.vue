<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { NSpace, NButton, NSpin, useMessage } from 'naive-ui'
import { ScheduleXCalendar } from '@schedule-x/vue'
import { createCalendar, viewDay, viewWeek } from '@schedule-x/calendar'
import { createDragAndDropPlugin } from '@schedule-x/drag-and-drop'
import { createResizePlugin } from '@schedule-x/resize'
import { formatISO } from 'date-fns'
import { useTimelineStore } from '@/stores/timeline'
import { useActivityStore } from '@/stores/activity'
import { ApiError } from '@/api/client'
import TimelineEntryForm from '@/components/TimelineEntryForm.vue'
import type { TimelineEntry } from '@/types/timeline'
import type { ActivitySession } from '@/types/activity'

import '@schedule-x/theme-default/dist/index.css'

const message = useMessage()
const timelineStore = useTimelineStore()
const activityStore = useActivityStore()

const showForm = ref(false)
const editingEntry = ref<TimelineEntry | null>(null)
const clickedTime = ref<string | undefined>(undefined)
const showSessions = ref(localStorage.getItem('showSessions') !== 'false')

const dragAndDrop = createDragAndDropPlugin()
const eventResize = createResizePlugin()

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

function sessionToEvent(s: ActivitySession) {
  return {
    id: `session-${s.id}`,
    title: s.app_name,
    start: isoToZoned(s.start_time),
    end: isoToZoned(s.end_time),
    calendarId: 'sessions',
    _options: { disableDND: true, disableResize: true },
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
  plugins: [dragAndDrop, eventResize],
  calendars: {
    timeline: {
      colorName: 'timeline',
      lightColors: { main: '#3B82F6', container: '#DBEAFE', onContainer: '#1E3A5F' },
      darkColors: { main: '#60A5FA', container: '#1E3A5F', onContainer: '#DBEAFE' },
    },
    sessions: {
      colorName: 'sessions',
      lightColors: { main: '#9CA3AF', container: '#F3F4F6', onContainer: '#4B5563' },
      darkColors: { main: '#6B7280', container: '#374151', onContainer: '#D1D5DB' },
    },
  },
  callbacks: {
    onEventClick(event) {
      if (String(event.id).startsWith('session-')) return
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

function syncEvents() {
  const entryEvents = timelineStore.entries.map(entryToEvent)
  const sessionEvents = showSessions.value
    ? activityStore.sessions.map(sessionToEvent)
    : []
  try {
    calendar.events.set([...sessionEvents, ...entryEvents])
  } catch {
    // events may not be initialized yet
  }
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
    <NSpace justify="end" style="margin-bottom: 12px">
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
/* Session events: render as full-width background layer, not side-by-side columns */
.sx__time-grid-event[data-event-id^="session-"] {
  width: 100% !important;
  inset-inline-start: 0 !important;
  z-index: 0 !important;
  opacity: 0.5;
  pointer-events: none;
}
</style>
