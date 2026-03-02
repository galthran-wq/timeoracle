<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { NSpace, NButton, NSpin, NText, NIcon, useMessage } from 'naive-ui'
import { ChatbubbleEllipsesOutline } from '@vicons/ionicons5'
import { ScheduleXCalendar } from '@schedule-x/vue'
import { createCalendar, viewDay, viewWeek } from '@schedule-x/calendar'
import { createDragAndDropPlugin } from '@schedule-x/drag-and-drop'
import { createResizePlugin } from '@schedule-x/resize'
import { createCurrentTimePlugin } from '@schedule-x/current-time'
import { formatISO } from 'date-fns'
import { useTimelineStore } from '@/stores/timeline'
import { useActivityStore } from '@/stores/activity'
import { useThemeStore } from '@/stores/theme'
import { ApiError } from '@/api/client'
import { createSessionLinesPlugin } from '@/plugins/sessionLines'
import ChatPanel from '@/components/ChatPanel.vue'
import TimelineEntryForm from '@/components/TimelineEntryForm.vue'
import TimeGridEvent from '@/components/TimeGridEvent.vue'
import type { TimelineEntry } from '@/types/timeline'

import { SESSION_PALETTE } from '@/constants/palette'

import '@schedule-x/theme-default/dist/index.css'

const message = useMessage()
const timelineStore = useTimelineStore()
const activityStore = useActivityStore()
const themeStore = useThemeStore()

const showForm = ref(false)
const editingEntry = ref<TimelineEntry | null>(null)
const clickedTime = ref<string | undefined>(undefined)
const clickPos = ref<{ x: number; y: number } | undefined>(undefined)
const showSessions = ref(localStorage.getItem('showSessions') !== 'false')
const showChat = ref(localStorage.getItem('showChat') === 'true')

function toggleChat() {
  showChat.value = !showChat.value
  localStorage.setItem('showChat', String(showChat.value))
}

const dragAndDrop = createDragAndDropPlugin()
const eventResize = createResizePlugin()
const currentTime = createCurrentTimePlugin()
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
    description: e.description ?? '',
    _label: e.label,
    _category: e.category ?? '',
    _color: e.color ?? '',
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
  isDark: themeStore.isDark,
  timezone: tz,
  events: [],
  plugins: [dragAndDrop, eventResize, sessionLines, currentTime],
  calendars: {
    timeline: {
      colorName: 'timeline',
      lightColors: { main: '#3B82F6', container: '#DBEAFE', onContainer: '#1E3A5F' },
      darkColors: { main: '#60A5FA', container: '#1E3A5F', onContainer: '#DBEAFE' },
    },
  },
  callbacks: {
    onEventClick(event, e) {
      const entry = timelineStore.entries.find((en) => en.id === String(event.id))
      if (entry) {
        const me = e as MouseEvent
        clickPos.value = { x: me.clientX, y: me.clientY }
        editingEntry.value = entry
        clickedTime.value = undefined
        showForm.value = true
      }
    },
    onClickDateTime(dateTime, e) {
      const me = e as MouseEvent
      clickPos.value = me ? { x: me.clientX, y: me.clientY } : undefined
      editingEntry.value = null
      clickedTime.value = new Date(dateTime.epochMilliseconds).toISOString()
      showForm.value = true
    },
    onSelectedDateUpdate(date) {
      timelineStore.selectedDate = date.toString()
    },
    onRangeUpdate(range) {
      const start = range.start as Temporal.ZonedDateTime
      const end = range.end as Temporal.ZonedDateTime
      const ms = end.epochMilliseconds - start.epochMilliseconds
      timelineStore.viewMode = ms > 86_400_000 ? 'week' : 'day'
      timelineStore.rangeStart = start.toPlainDate().toString()
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
  return [...map.entries()].map(([app, i]) => {
    const color = SESSION_PALETTE[i % SESSION_PALETTE.length]
    const container = themeStore.isDark ? color.darkContainer : color.container
    return { app, main: color.main, container }
  })
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
watch(() => themeStore.isDark, (dark) => calendar.setTheme(dark ? 'dark' : 'light'))

watch(
  [() => timelineStore.rangeStart, () => timelineStore.viewMode],
  ([date, range]) => activityStore.fetchSessions(date, range),
)

onMounted(async () => {
  await Promise.all([
    timelineStore.fetchEntries(),
    activityStore.fetchSessions(timelineStore.rangeStart, timelineStore.viewMode),
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

function openCreate(e: MouseEvent) {
  clickPos.value = { x: e.clientX, y: e.clientY }
  editingEntry.value = null
  clickedTime.value = undefined
  showForm.value = true
}
</script>

<template>
  <div style="height: 100%; display: flex">
    <div style="flex: 1; min-width: 0; display: flex; flex-direction: column">
    <NSpace justify="end" align="center" style="margin-bottom: 16px">
      <NSpace v-if="showSessions && sessionApps.length" :size="8" align="center">
        <template v-for="item in sessionApps" :key="item.app">
          <NSpace :size="4" align="center">
            <div class="legend-dot" :style="{ backgroundColor: item.container, borderLeftColor: item.main }" />
            <NText depth="3" style="font-size: 12px">{{ item.app }}</NText>
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
      <NButton :type="showChat ? 'primary' : 'default'" @click="toggleChat">
        <template #icon>
          <NIcon><ChatbubbleEllipsesOutline /></NIcon>
        </template>
        Agent
      </NButton>
    </NSpace>

    <NSpin :show="timelineStore.loading" style="flex: 1; min-height: 0">
      <div style="height: 100%; min-height: 600px">
        <ScheduleXCalendar :calendar-app="calendar">
          <template #timeGridEvent="{ calendarEvent }">
            <TimeGridEvent
              :calendar-event="calendarEvent"
            />
          </template>
        </ScheduleXCalendar>
      </div>
    </NSpin>

    <TimelineEntryForm
      v-model:show="showForm"
      :entry="editingEntry"
      :date="timelineStore.selectedDate"
      :default-start-time="clickedTime"
      :click-pos="clickPos"
      @save="handleSave"
      @delete="handleDelete"
    />
    </div>

    <ChatPanel v-if="showChat" />
  </div>
</template>
