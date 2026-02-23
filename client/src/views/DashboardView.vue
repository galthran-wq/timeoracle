<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NSpace, NButton, NList, NListItem, NText, NCard, NSpin, NEmpty } from 'naive-ui'
import { useRouter } from 'vue-router'
import { format } from 'date-fns'
import DaemonStatus from '@/components/DaemonStatus.vue'
import { useActivityStore } from '@/stores/activity'
import { listEntries } from '@/api/timeline'
import type { TimelineEntry } from '@/types/timeline'

const router = useRouter()
const activityStore = useActivityStore()
const todayEntries = ref<TimelineEntry[]>([])
const loading = ref(true)

onMounted(async () => {
  const today = format(new Date(), 'yyyy-MM-dd')
  await Promise.all([
    activityStore.fetchStatus(),
    listEntries({ date: today }).then((res) => {
      todayEntries.value = res.entries
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
    </NSpace>
  </NSpin>
</template>
