import { ref } from 'vue'
import { defineStore } from 'pinia'
import { listEvents, listSessions, getStatus } from '@/api/activity'
import type { ActivityEvent, ActivityEventType, ActivitySession, ActivityStatus } from '@/types/activity'

export const useActivityStore = defineStore('activity', () => {
  const events = ref<ActivityEvent[]>([])
  const totalCount = ref(0)
  const loading = ref(false)
  const status = ref<ActivityStatus | null>(null)
  const sessions = ref<ActivitySession[]>([])
  const sessionsLoading = ref(false)

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

  async function fetchSessions(date: string) {
    sessionsLoading.value = true
    try {
      const res = await listSessions({ date, range: 'day', limit: 500 })
      sessions.value = res.sessions
    } finally {
      sessionsLoading.value = false
    }
  }

  async function fetchStatus() {
    status.value = await getStatus()
  }

  return { events, totalCount, loading, status, sessions, sessionsLoading, fetchEvents, fetchSessions, fetchStatus }
})
