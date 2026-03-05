<script setup lang="ts">
import { computed } from 'vue'
import { NCard, NStatistic, NSpace, NBadge, NText } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import { formatDistanceToNow } from 'date-fns'
import type { ActivityStatus } from '@/types/activity'

const { t } = useI18n()

const props = defineProps<{ status: ActivityStatus | null; loading: boolean }>()

const isActive = computed(() => {
  if (!props.status?.last_event_at) return false
  const diff = Date.now() - new Date(props.status.last_event_at).getTime()
  return diff < 5 * 60 * 1000
})

const lastEventText = computed(() => {
  if (!props.status?.last_event_at) return t('daemon.noEventsYet')
  return formatDistanceToNow(new Date(props.status.last_event_at), { addSuffix: true })
})
</script>

<template>
  <NCard :title="t('daemon.title')">
    <NSpace vertical :size="16">
      <NSpace align="center" :size="8">
        <NBadge :dot="true" :type="isActive ? 'success' : 'error'" />
        <NText>{{ isActive ? t('daemon.active') : t('daemon.inactive') }}</NText>
      </NSpace>
      <NStatistic :label="t('daemon.lastActivity')" :value="lastEventText" />
      <NStatistic :label="t('daemon.eventsToday')" :value="status?.events_today ?? 0" />
    </NSpace>
  </NCard>
</template>
