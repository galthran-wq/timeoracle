import { ref } from 'vue'
import { defineStore } from 'pinia'
import { listEvents, getStatus } from '@/api/activity'
import type { ActivityEvent, ActivityEventType, ActivityStatus } from '@/types/activity'

export const useActivityStore = defineStore('activity', () => {
  const events = ref<ActivityEvent[]>([])
  const totalCount = ref(0)
  const loading = ref(false)
  const status = ref<ActivityStatus | null>(null)

  async function fetchEvents(params: {
    start: string
    end: string
    limit?: number
    offset?: number
    event_type?: ActivityEventType
    app_name?: string
  }) {
    loading.value = true
    try {
      const res = await listEvents(params)
      events.value = res.events
      totalCount.value = res.total_count
    } finally {
      loading.value = false
    }
  }

  async function fetchStatus() {
    status.value = await getStatus()
  }

  return { events, totalCount, loading, status, fetchEvents, fetchStatus }
})
