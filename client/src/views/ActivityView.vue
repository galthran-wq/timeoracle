<script setup lang="ts">
import { h, ref, onMounted, watch } from 'vue'
import {
  NSpace,
  NDatePicker,
  NSelect,
  NInput,
  NDataTable,
  NPagination,
  NTag,
  NSpin,
} from 'naive-ui'
import type { DataTableColumn } from 'naive-ui'
import { format, startOfDay, endOfDay } from 'date-fns'
import { useActivityStore } from '@/stores/activity'
import type { ActivityEvent, ActivityEventType } from '@/types/activity'

const activityStore = useActivityStore()

const PAGE_SIZE = 50

const dateRange = ref<[number, number]>([startOfDay(new Date()).getTime(), endOfDay(new Date()).getTime()])
const eventType = ref<ActivityEventType | null>(null)
const appName = ref('')
const page = ref(1)

const typeOptions = [
  { label: 'All Types', value: '' },
  { label: 'Active Window', value: 'active_window' },
  { label: 'Idle Start', value: 'idle_start' },
  { label: 'Idle End', value: 'idle_end' },
]

const tagTypes: Record<string, 'success' | 'warning' | 'info'> = {
  active_window: 'success',
  idle_start: 'warning',
  idle_end: 'info',
}

const columns: DataTableColumn<ActivityEvent>[] = [
  {
    title: 'Time',
    key: 'timestamp',
    width: 140,
    render: (row) => format(new Date(row.timestamp), 'HH:mm:ss'),
  },
  {
    title: 'Type',
    key: 'event_type',
    width: 140,
    render: (row) =>
      h(NTag, { type: tagTypes[row.event_type] ?? 'default', size: 'small' }, () =>
        row.event_type.replace('_', ' '),
      ),
  },
  { title: 'App', key: 'app_name', width: 160, ellipsis: { tooltip: true } },
  { title: 'Window Title', key: 'window_title', ellipsis: { tooltip: true } },
  { title: 'URL', key: 'url', width: 200, ellipsis: { tooltip: true } },
]

async function fetchData() {
  const [startMs, endMs] = dateRange.value
  await activityStore.fetchEvents({
    start: new Date(startMs).toISOString(),
    end: new Date(endMs).toISOString(),
    limit: PAGE_SIZE,
    offset: (page.value - 1) * PAGE_SIZE,
    event_type: eventType.value || undefined,
    app_name: appName.value || undefined,
  })
}

watch([dateRange, eventType, appName], () => {
  page.value = 1
  fetchData()
})

watch(page, fetchData)

onMounted(fetchData)
</script>

<template>
  <NSpace vertical :size="16">
    <NSpace :size="12" align="center">
      <NDatePicker
        v-model:value="dateRange"
        type="daterange"
        clearable
        style="width: 300px"
      />
      <NSelect
        :value="eventType ?? ''"
        :options="typeOptions"
        style="width: 160px"
        @update:value="(v: string) => (eventType = (v || null) as ActivityEventType | null)"
      />
      <NInput
        v-model:value="appName"
        placeholder="Filter by app name"
        clearable
        style="width: 200px"
      />
    </NSpace>

    <NSpin :show="activityStore.loading">
      <NDataTable
        :columns="columns"
        :data="activityStore.events"
        :bordered="false"
        :row-key="(row: ActivityEvent) => row.id"
        size="small"
      />
    </NSpin>

    <NSpace justify="end">
      <NPagination
        v-model:page="page"
        :page-count="Math.max(1, Math.ceil(activityStore.totalCount / PAGE_SIZE))"
        :page-slot="7"
      />
    </NSpace>
  </NSpace>
</template>
