<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { NSpace, NButton, NSpin, useMessage } from 'naive-ui'
import { ScheduleXCalendar } from '@schedule-x/vue'
import { createCalendar, viewDay, viewWeek } from '@schedule-x/calendar'
import { createDragAndDropPlugin } from '@schedule-x/drag-and-drop'
import { createResizePlugin } from '@schedule-x/resize'
import { format, formatISO, parseISO } from 'date-fns'
import { useTimelineStore } from '@/stores/timeline'
import { ApiError } from '@/api/client'
import TimelineEntryForm from '@/components/TimelineEntryForm.vue'
import type { TimelineEntry } from '@/types/timeline'

import '@schedule-x/theme-default/dist/index.css'

const message = useMessage()
const timelineStore = useTimelineStore()

const showForm = ref(false)
const editingEntry = ref<TimelineEntry | null>(null)
const clickedTime = ref<string | undefined>(undefined)

const dragAndDrop = createDragAndDropPlugin()
const eventResize = createResizePlugin()

function entryToEvent(e: TimelineEntry) {
  return {
    id: e.id,
    title: e.category ? `${e.label} (${e.category})` : e.label,
    start: format(parseISO(e.start_time), 'yyyy-MM-dd HH:mm'),
    end: format(parseISO(e.end_time), 'yyyy-MM-dd HH:mm'),
  }
}

const calendar = createCalendar({
  views: [viewDay, viewWeek],
  defaultView: viewDay.name,
  selectedDate: timelineStore.selectedDate,
  events: [],
  plugins: [dragAndDrop, eventResize],
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
      clickedTime.value = dateTime
      showForm.value = true
    },
    onSelectedDateUpdate(date) {
      timelineStore.selectedDate = date
    },
    async onEventUpdate(updatedEvent) {
      try {
        const startStr = String(updatedEvent.start).replace(' ', 'T')
        const endStr = String(updatedEvent.end).replace(' ', 'T')
        const entryDate = startStr.substring(0, 10)
        await timelineStore.updateEntry(String(updatedEvent.id), {
          start_time: formatISO(new Date(startStr)),
          end_time: formatISO(new Date(endStr)),
          date: entryDate,
        })
      } catch (e) {
        message.error(e instanceof ApiError ? e.message : 'Failed to update entry')
        await timelineStore.fetchEntries()
      }
    },
  },
})

function syncEvents() {
  const events = timelineStore.entries.map(entryToEvent)
  // Clear and re-set all events
  try {
    const existing = calendar.events.getAll()
    for (const ev of existing) {
      calendar.events.remove(String(ev.id))
    }
  } catch {
    // events may not be initialized yet
  }
  for (const ev of events) {
    calendar.events.add(ev)
  }
}

watch(() => timelineStore.entries, syncEvents, { deep: true })

onMounted(async () => {
  await timelineStore.fetchEntries()
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
      await timelineStore.updateEntry(editingEntry.value.id, payload)
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
