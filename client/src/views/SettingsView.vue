<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import {
  NCard,
  NSpace,
  NInputNumber,
  NSelect,
  NButton,
  NMenu,
  NSpin,
  NSwitch,
  NTooltip,
  NIcon,
  NInput,
  NColorPicker,
  useMessage,
} from 'naive-ui'
import type { MenuOption } from 'naive-ui'
import { InformationCircleOutline, TrashOutline } from '@vicons/ionicons5'
import type { SessionConfig } from '@/types/settings'
import type { CategoryConfig } from '@/constants/categories'
import { getSessionConfig, updateSessionConfig, getDefaultCategories } from '@/api/settings'
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
  { label: 'Categories', key: 'categories' },
  { label: 'Integrations', key: 'integrations' },
]

const newCatName = ref('')
const newCatColor = ref('#78716c')
const newRule = ref('')

const defaultCategories = ref<Record<string, CategoryConfig>>({})
const editingCategories = ref<Record<string, CategoryConfig>>({})
const editingRules = ref<string[]>([])
const showDeprecated = ref(false)

const activeCategories = computed(() =>
  Object.entries(editingCategories.value).filter(([, cfg]) => !cfg.deprecated),
)
const deprecatedCategories = computed(() =>
  Object.entries(editingCategories.value).filter(([, cfg]) => cfg.deprecated),
)

function initCategoryEditor() {
  const cats = config.value.categories ?? defaultCategories.value
  editingCategories.value = JSON.parse(JSON.stringify(cats))
  editingRules.value = [...(config.value.classification_rules ?? [])]
}

function addCategory() {
  const name = newCatName.value.trim()
  if (!name) return
  if (editingCategories.value[name]) {
    message.warning(`Category "${name}" already exists`)
    return
  }
  editingCategories.value[name] = { color: newCatColor.value }
  newCatName.value = ''
  newCatColor.value = '#78716c'
}

function deprecateCategory(name: string) {
  editingCategories.value[name] = { ...editingCategories.value[name], deprecated: true }
  editingCategories.value = { ...editingCategories.value }
}

function restoreCategory(name: string) {
  const { deprecated: _, ...rest } = editingCategories.value[name] as CategoryConfig & { deprecated?: boolean }
  editingCategories.value[name] = rest as CategoryConfig
  editingCategories.value = { ...editingCategories.value }
}

function addRule() {
  const rule = newRule.value.trim()
  if (!rule) return
  editingRules.value.push(rule)
  newRule.value = ''
}

function deleteRule(index: number) {
  editingRules.value.splice(index, 1)
}

let initializing = false
let autoSaveTimer: ReturnType<typeof setTimeout> | null = null

async function autoSave() {
  saving.value = true
  try {
    const updated = await updateSessionConfig({
      ...config.value,
      categories: editingCategories.value,
      classification_rules: editingRules.value,
    })
    initializing = true
    config.value = updated
    nextTick(() => { initializing = false })
  } catch {
    message.error('Failed to save settings')
  } finally {
    saving.value = false
  }
}

function scheduleAutoSave() {
  if (initializing) return
  if (autoSaveTimer) clearTimeout(autoSaveTimer)
  autoSaveTimer = setTimeout(autoSave, 600)
}

watch(config, scheduleAutoSave, { deep: true })
watch(editingCategories, scheduleAutoSave, { deep: true })
watch(editingRules, scheduleAutoSave, { deep: true })

onUnmounted(() => {
  if (autoSaveTimer) clearTimeout(autoSaveTimer)
})

async function loadConfig() {
  loading.value = true
  initializing = true
  try {
    const [loaded, defaults] = await Promise.all([getSessionConfig(), getDefaultCategories()])
    if (!loaded.timezone) {
      loaded.timezone = browserTz
    }
    config.value = loaded
    defaultCategories.value = defaults
    initCategoryEditor()
  } catch {
    message.error('Failed to load session config')
  } finally {
    loading.value = false
    nextTick(() => { initializing = false })
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

              <NButton text size="small" @click="resetDefaults">Reset to defaults</NButton>
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

            </NSpace>
          </NCard>
        </template>
        <template v-else-if="activeTab === 'categories'">
          <NCard title="Categories">
            <NSpace vertical :size="16">
              <div
                v-for="[name, cfg] in activeCategories"
                :key="name"
                class="category-row"
              >
                <span class="color-swatch" :style="{ backgroundColor: cfg.color }" />
                <span class="category-name">{{ name }}</span>
                <NColorPicker
                  :value="cfg.color"
                  :modes="['hex']"
                  size="small"
                  style="width: 80px"
                  @update:value="(v: string) => (cfg.color = v)"
                />
                <NTooltip>
                  <template #trigger>
                    <NSwitch
                      :value="cfg.work !== false"
                      size="small"
                      @update:value="(v: boolean) => (cfg.work = v)"
                    />
                  </template>
                  Work category
                </NTooltip>
                <NButton text size="small" @click="deprecateCategory(name)">
                  <template #icon><NIcon :size="16"><TrashOutline /></NIcon></template>
                </NButton>
              </div>

              <div class="category-row add-row">
                <NInput
                  v-model:value="newCatName"
                  placeholder="New category"
                  size="small"
                  style="width: 140px"
                  @keydown.enter.prevent="addCategory"
                />
                <NColorPicker
                  v-model:value="newCatColor"
                  :modes="['hex']"
                  size="small"
                  style="width: 80px"
                />
                <NButton size="small" @click="addCategory">Add</NButton>
              </div>

              <template v-if="deprecatedCategories.length">
                <NButton
                  text
                  size="small"
                  @click="showDeprecated = !showDeprecated"
                >
                  {{ showDeprecated ? 'Hide' : 'Show' }} {{ deprecatedCategories.length }} hidden {{ deprecatedCategories.length === 1 ? 'category' : 'categories' }}
                </NButton>
                <template v-if="showDeprecated">
                  <div
                    v-for="[name, cfg] in deprecatedCategories"
                    :key="name"
                    class="category-row deprecated"
                  >
                    <span class="color-swatch" :style="{ backgroundColor: cfg.color }" />
                    <span class="category-name">{{ name }}</span>
                    <NButton text size="small" @click="restoreCategory(name)">Restore</NButton>
                  </div>
                </template>
              </template>
            </NSpace>
          </NCard>

          <NCard title="Classification Rules" style="margin-top: 16px">
            <NSpace vertical :size="12">
              <div v-for="(rule, i) in editingRules" :key="i" class="rule-row">
                <span class="rule-text">{{ rule }}</span>
                <NButton text size="small" @click="deleteRule(i)">
                  <template #icon><NIcon :size="16"><TrashOutline /></NIcon></template>
                </NButton>
              </div>

              <div class="rule-row">
                <NInput
                  v-model:value="newRule"
                  placeholder="e.g. VS Code is always Work"
                  size="small"
                  style="flex: 1"
                  @keydown.enter.prevent="addRule"
                />
                <NButton size="small" @click="addRule">Add</NButton>
              </div>
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

.category-row {
  display: flex;
  align-items: center;
  gap: var(--to-space-sm);
}

.category-row.deprecated {
  opacity: 0.5;
}

.category-row .color-swatch {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  flex-shrink: 0;
}

.category-name {
  flex: 1;
  font-weight: 500;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.add-row {
  padding-top: var(--to-space-sm);
  border-top: 1px solid var(--to-border-color, rgba(128, 128, 128, 0.2));
}

.rule-row {
  display: flex;
  align-items: center;
  gap: var(--to-space-sm);
}

.rule-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
