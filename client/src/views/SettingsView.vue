<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  NCard,
  NSpace,
  NInputNumber,
  NSelect,
  NButton,
  NMenu,
  NSpin,
  NTooltip,
  NIcon,
  useMessage,
} from 'naive-ui'
import type { MenuOption } from 'naive-ui'
import { InformationCircleOutline } from '@vicons/ionicons5'
import type { SessionConfig } from '@/types/settings'
import { getSessionConfig, updateSessionConfig } from '@/api/settings'
import TelegramCard from '@/components/integrations/TelegramCard.vue'

const message = useMessage()

const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone

const DEFAULTS: SessionConfig = {
  merge_gap_seconds: 300,
  min_session_seconds: 5,
  noise_threshold_seconds: 120,
  day_start_hour: 0,
  timezone: browserTz,
}

const timezoneOptions = Intl.supportedValuesOf('timeZone').map((tz) => ({ label: tz, value: tz }))

function formatHour(h: number | null): string {
  if (h === null) return ''
  const suffix = h < 12 ? 'AM' : 'PM'
  const display = h === 0 ? 12 : h > 12 ? h - 12 : h
  return `${display}:00 ${suffix}`
}

function parseHour(value: string): number {
  const trimmed = value.trim()
  if (!trimmed) return 0
  const match = trimmed.match(/^(\d{1,2})(?::\d{2})?\s*(am|pm)?$/i)
  if (!match) {
    const fallback = Number.parseInt(trimmed, 10)
    return Number.isNaN(fallback) ? 0 : Math.max(0, Math.min(23, fallback))
  }
  let hour = Number.parseInt(match[1], 10)
  if (Number.isNaN(hour)) return 0
  const meridiem = match[2]?.toLowerCase()
  if (meridiem) {
    if (hour === 12) {
      hour = meridiem === 'am' ? 0 : 12
    } else if (meridiem === 'pm') {
      hour = hour + 12
    }
  }
  return Math.max(0, Math.min(23, hour))
}

const activeTab = ref('sessions')
const loading = ref(false)
const saving = ref(false)

const config = ref<SessionConfig>({ ...DEFAULTS })

const tabOptions: MenuOption[] = [
  { label: 'Activity Sessions', key: 'sessions' },
  { label: 'Day Boundary', key: 'day-boundary' },
  { label: 'Integrations', key: 'integrations' },
]

async function loadConfig() {
  loading.value = true
  try {
    const loaded = await getSessionConfig()
    if (!loaded.timezone) {
      loaded.timezone = browserTz
    }
    config.value = loaded
  } catch {
    message.error('Failed to load session config')
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    config.value = await updateSessionConfig(config.value)
    message.success('Settings saved')
  } catch {
    message.error('Failed to save settings')
  } finally {
    saving.value = false
  }
}

function resetDefaults() {
  config.value = { ...DEFAULTS }
}

onMounted(loadConfig)
</script>

<template>
  <div class="settings-layout">
    <div class="settings-sidebar">
      <div class="settings-title">Settings</div>
      <NMenu
        :value="activeTab"
        :options="tabOptions"
        @update:value="(k: string) => (activeTab = k)"
      />
    </div>
    <div class="settings-content">
      <NSpin :show="loading">
        <template v-if="activeTab === 'sessions'">
          <NCard title="Activity Sessions">
            <NSpace vertical :size="24">
              <div class="setting-field">
                <div class="setting-label">
                  Merge gap (seconds)
                  <NTooltip>
                    <template #trigger>
                      <NIcon :size="16" class="info-icon"><InformationCircleOutline /></NIcon>
                    </template>
                    If the same app appears again within this many seconds, the sessions are merged into one. Higher = fewer, longer sessions.
                  </NTooltip>
                </div>
                <NInputNumber
                  v-model:value="config.merge_gap_seconds"
                  :min="1"
                  :max="3600"
                  :step="10"
                  style="width: 200px"
                />
              </div>

              <div class="setting-field">
                <div class="setting-label">
                  Min session duration (seconds)
                  <NTooltip>
                    <template #trigger>
                      <NIcon :size="16" class="info-icon"><InformationCircleOutline /></NIcon>
                    </template>
                    Sessions shorter than this are discarded. Filters out accidental window switches.
                  </NTooltip>
                </div>
                <NInputNumber
                  v-model:value="config.min_session_seconds"
                  :min="0"
                  :max="600"
                  :step="1"
                  style="width: 200px"
                />
              </div>

              <div class="setting-field">
                <div class="setting-label">
                  Noise threshold (seconds)
                  <NTooltip>
                    <template #trigger>
                      <NIcon :size="16" class="info-icon"><InformationCircleOutline /></NIcon>
                    </template>
                    Sessions shorter than this that are no longer active get dropped as noise. Reduces clutter from brief app appearances.
                  </NTooltip>
                </div>
                <NInputNumber
                  v-model:value="config.noise_threshold_seconds"
                  :min="0"
                  :max="3600"
                  :step="10"
                  style="width: 200px"
                />
              </div>

              <NSpace :size="12">
                <NButton type="primary" :loading="saving" @click="saveConfig">Save</NButton>
                <NButton @click="resetDefaults">Reset to defaults</NButton>
              </NSpace>
            </NSpace>
          </NCard>
        </template>
        <template v-else-if="activeTab === 'day-boundary'">
          <NCard title="Day Boundary">
            <NSpace vertical :size="24">
              <div class="setting-field">
                <div class="setting-label">
                  Day ends at
                  <NTooltip>
                    <template #trigger>
                      <NIcon :size="16" class="info-icon"><InformationCircleOutline /></NIcon>
                    </template>
                    Late-night activity before this hour counts as the previous day.
                  </NTooltip>
                </div>
                <NInputNumber
                  v-model:value="config.day_start_hour"
                  :min="0"
                  :max="23"
                  :step="1"
                  style="width: 200px"
                  :format="formatHour"
                  :parse="parseHour"
                />
              </div>

              <div class="setting-field">
                <div class="setting-label">
                  Timezone
                  <NTooltip>
                    <template #trigger>
                      <NIcon :size="16" class="info-icon"><InformationCircleOutline /></NIcon>
                    </template>
                    Your local timezone, used to determine when the day boundary occurs.
                  </NTooltip>
                </div>
                <NSelect
                  v-model:value="config.timezone"
                  :options="timezoneOptions"
                  filterable
                  style="width: 300px"
                />
              </div>

              <NSpace :size="12">
                <NButton type="primary" :loading="saving" @click="saveConfig">Save</NButton>
              </NSpace>
            </NSpace>
          </NCard>
        </template>
        <template v-else-if="activeTab === 'integrations'">
          <TelegramCard />
        </template>
      </NSpin>
    </div>
  </div>
</template>

<style scoped>
.settings-layout {
  display: flex;
  gap: var(--to-space-xl);
  height: 100%;
}

.settings-sidebar {
  width: 200px;
  flex-shrink: 0;
}

.settings-title {
  font-size: var(--to-text-lg);
  font-weight: 600;
  margin-bottom: var(--to-space-md);
}

.settings-content {
  flex: 1;
  max-width: 600px;
}

.setting-field {
  display: flex;
  flex-direction: column;
  gap: var(--to-space-sm);
}

.setting-label {
  font-size: var(--to-text-base);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: var(--to-space-xs);
}

.info-icon {
  cursor: help;
  opacity: 0.5;
  vertical-align: middle;
}
</style>
