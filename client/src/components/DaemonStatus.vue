<script setup lang="ts">
import { computed } from 'vue'
import { NCard, NStatistic, NSpace, NBadge, NText } from 'naive-ui'
import { formatDistanceToNow } from 'date-fns'
import type { ActivityStatus } from '@/types/activity'

const props = defineProps<{ status: ActivityStatus | null; loading: boolean }>()

const isActive = computed(() => {
  if (!props.status?.last_event_at) return false
  const diff = Date.now() - new Date(props.status.last_event_at).getTime()
  return diff < 5 * 60 * 1000
})

const lastEventText = computed(() => {
  if (!props.status?.last_event_at) return 'No events yet'
  return formatDistanceToNow(new Date(props.status.last_event_at), { addSuffix: true })
})
</script>

<template>
  <NCard title="Daemon Status">
    <NSpace vertical :size="16">
      <NSpace align="center" :size="8">
        <NBadge :dot="true" :type="isActive ? 'success' : 'error'" />
        <NText>{{ isActive ? 'Active' : 'Inactive' }}</NText>
      </NSpace>
      <NStatistic label="Last Activity" :value="lastEventText" />
      <NStatistic label="Events Today" :value="status?.events_today ?? 0" />
    </NSpace>
  </NCard>
</template>
