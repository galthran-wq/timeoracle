import { ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { format } from 'date-fns'
import * as api from '@/api/timeline'
import type { TimelineEntry, TimelineEntryCreate, TimelineEntryUpdate } from '@/types/timeline'

export const useTimelineStore = defineStore('timeline', () => {
  const selectedDate = ref(format(new Date(), 'yyyy-MM-dd'))
  const rangeStart = ref(selectedDate.value)
  const viewMode = ref<'day' | 'week'>('day')
  const entries = ref<TimelineEntry[]>([])
  const totalCount = ref(0)
  const loading = ref(false)

  async function fetchEntries() {
    loading.value = true
    try {
      const res = await api.listEntries({ date: rangeStart.value, range: viewMode.value, limit: 500 })
      entries.value = res.entries
      totalCount.value = res.total_count
    } finally {
      loading.value = false
    }
  }

  async function createEntry(data: TimelineEntryCreate): Promise<TimelineEntry> {
    const entry = await api.createEntry(data)
    await fetchEntries()
    return entry
  }

  async function updateEntry(id: string, data: TimelineEntryUpdate): Promise<TimelineEntry> {
    const entry = await api.updateEntry(id, data)
    await fetchEntries()
    return entry
  }

  async function deleteEntry(id: string): Promise<void> {
    await api.deleteEntry(id)
    await fetchEntries()
  }

  function toCalendarEvents() {
    return entries.value.map((e) => ({
      id: e.id,
      title: e.label,
      start: e.start_time,
      end: e.end_time,
      calendarId: e.category ?? 'default',
      _color: e.color,
      _entry: e,
    }))
  }

  watch([rangeStart, viewMode], fetchEntries)

  return {
    selectedDate,
    rangeStart,
    viewMode,
    entries,
    totalCount,
    loading,
    fetchEntries,
    createEntry,
    updateEntry,
    deleteEntry,
    toCalendarEvents,
  }
})
