<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NSpace, NButton, NList, NListItem, NText, NCard, NSpin, NEmpty } from 'naive-ui'
import { useRouter } from 'vue-router'
import { format, differenceInMinutes } from 'date-fns'
import DaemonStatus from '@/components/DaemonStatus.vue'
import { useActivityStore } from '@/stores/activity'
import { listEntries } from '@/api/timeline'
import { listSessions } from '@/api/activity'
import type { TimelineEntry } from '@/types/timeline'
import type { ActivitySession } from '@/types/activity'

const router = useRouter()
const activityStore = useActivityStore()
const todayEntries = ref<TimelineEntry[]>([])
const todaySessions = ref<ActivitySession[]>([])
const loading = ref(true)

function formatDuration(start: string, end: string): string {
  const mins = differenceInMinutes(new Date(end), new Date(start))
  if (mins < 60) return `${mins}m`
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

onMounted(async () => {
  const today = format(new Date(), 'yyyy-MM-dd')
  await Promise.all([
    activityStore.fetchStatus(),
    listEntries({ date: today }).then((res) => {
      todayEntries.value = res.entries
    }),
    listSessions({ date: today, limit: 50 }).then((res) => {
      todaySessions.value = res.sessions
    }),
  ])
  loading.value = false
})
</script>

<template>
  <NSpin :show="loading">
    <NSpace vertical :size="24">
      <DaemonStatus :status="activityStore.status" :loading="loading" />

      <NCard title="Today's Timeline">
        <template #header-extra>
          <NButton text type="primary" @click="router.push({ name: 'timeline' })">
            View Calendar
          </NButton>
        </template>
        <NEmpty v-if="!todayEntries.length" description="No timeline entries today" />
        <NList v-else>
          <NListItem v-for="entry in todayEntries" :key="entry.id">
            <NSpace align="center" :size="12">
              <div
                v-if="entry.color"
                :style="{
                  width: '12px',
                  height: '12px',
                  borderRadius: '2px',
                  backgroundColor: entry.color,
                }"
              />
              <NText strong>{{ entry.label }}</NText>
              <NText depth="3">
                {{ format(new Date(entry.start_time), 'HH:mm') }} –
                {{ format(new Date(entry.end_time), 'HH:mm') }}
              </NText>
              <NText v-if="entry.category" depth="3">· {{ entry.category }}</NText>
            </NSpace>
          </NListItem>
        </NList>
      </NCard>

      <NCard title="Today's Activity">
        <NEmpty v-if="!todaySessions.length" description="No activity recorded today" />
        <NList v-else>
          <NListItem v-for="session in todaySessions" :key="session.id">
            <NSpace align="center" :size="12">
              <div
                :style="{
                  width: '12px',
                  height: '12px',
                  borderRadius: '2px',
                  backgroundColor: '#9CA3AF',
                }"
              />
              <NText strong>{{ session.app_name }}</NText>
              <NText depth="3">
                {{ format(new Date(session.start_time), 'HH:mm') }} –
                {{ format(new Date(session.end_time), 'HH:mm') }}
              </NText>
              <NText depth="3">· {{ formatDuration(session.start_time, session.end_time) }}</NText>
            </NSpace>
          </NListItem>
        </NList>
      </NCard>
    </NSpace>
  </NSpin>
</template>
