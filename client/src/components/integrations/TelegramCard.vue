<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { NCard, NButton, NSpace, NText, useMessage } from 'naive-ui'
import { useIntegrationsStore } from '@/stores/integrations'

const store = useIntegrationsStore()
const message = useMessage()

const connecting = ref(false)
const disconnecting = ref(false)
const deepLink = ref<string | null>(null)
const remaining = ref(0)
let pollTimer: ReturnType<typeof setInterval> | null = null
let countdownTimer: ReturnType<typeof setInterval> | null = null

const isConnected = computed(() => store.telegram?.is_connected ?? false)
const displayName = computed(() => store.telegram?.display_name ?? null)
const connectedAt = computed(() => {
  const raw = store.telegram?.connected_at
  if (!raw) return null
  return new Date(raw).toLocaleDateString()
})

async function startConnect() {
  connecting.value = true
  try {
    const res = await store.startTelegramConnect()
    deepLink.value = res.deep_link
    remaining.value = res.expires_in_seconds

    countdownTimer = setInterval(() => {
      remaining.value--
      if (remaining.value <= 0) {
        stopTimers()
        deepLink.value = null
        connecting.value = false
        message.warning('Link expired. Click Connect to try again.')
      }
    }, 1000)

    pollTimer = setInterval(async () => {
      await store.load()
      if (store.telegram?.is_connected) {
        stopTimers()
        deepLink.value = null
        connecting.value = false
        message.success('Telegram connected!')
      }
    }, 3000)
  } catch {
    message.error('Failed to start Telegram connection')
    connecting.value = false
  }
}

async function doDisconnect() {
  disconnecting.value = true
  try {
    const res = await store.telegramDisconnect()
    if (res.success) {
      message.success('Telegram disconnected')
    }
  } catch {
    message.error('Failed to disconnect')
  } finally {
    disconnecting.value = false
  }
}

function cancelConnect() {
  stopTimers()
  deepLink.value = null
  connecting.value = false
}

function stopTimers() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

function formatRemaining(s: number): string {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${sec.toString().padStart(2, '0')}`
}

onMounted(() => store.load())
onUnmounted(() => stopTimers())
</script>

<template>
  <NCard>
    <div class="integration-card">
      <div class="integration-header">
        <div class="integration-icon">
          <svg viewBox="0 0 24 24" width="28" height="28" fill="currentColor">
            <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
          </svg>
        </div>
        <div class="integration-info">
          <div class="integration-name">Telegram</div>
          <NText v-if="isConnected" depth="3" class="integration-desc">
            Connected as {{ displayName ?? 'Unknown' }}
            <span v-if="connectedAt"> &middot; since {{ connectedAt }}</span>
          </NText>
          <NText v-else depth="3" class="integration-desc">
            Connect to receive alerts from the guard bot
          </NText>
        </div>
        <div class="integration-status">
          <span v-if="isConnected" class="status-badge connected">Connected</span>
        </div>
      </div>

      <div v-if="deepLink && connecting" class="connect-flow">
        <div class="deep-link-box">
          <NText depth="3">Open this link in Telegram to connect:</NText>
          <a :href="deepLink" target="_blank" rel="noopener" class="deep-link">{{ deepLink }}</a>
          <NText depth="3" class="expires-text">
            Expires in {{ formatRemaining(remaining) }}
          </NText>
        </div>
        <NSpace :size="8">
          <NButton tag="a" :href="deepLink" target="_blank" type="primary" size="small">
            Open in Telegram
          </NButton>
          <NButton size="small" @click="cancelConnect">Cancel</NButton>
        </NSpace>
      </div>

      <div v-else class="integration-actions">
        <NButton
          v-if="!isConnected"
          type="primary"
          size="small"
          :loading="connecting"
          @click="startConnect"
        >
          Connect
        </NButton>
        <NButton
          v-else
          size="small"
          :loading="disconnecting"
          @click="doDisconnect"
        >
          Disconnect
        </NButton>
      </div>
    </div>
  </NCard>
</template>

<style scoped>
.integration-card {
  display: flex;
  flex-direction: column;
  gap: var(--to-space-md);
}

.integration-header {
  display: flex;
  align-items: center;
  gap: var(--to-space-md);
}

.integration-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--to-radius-md);
  background: #229ED9;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.integration-info {
  flex: 1;
  min-width: 0;
}

.integration-name {
  font-size: var(--to-text-lg);
  font-weight: 600;
}

.integration-desc {
  font-size: var(--to-text-sm);
}

.status-badge {
  font-size: var(--to-text-xs);
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--to-radius-sm);
}

.status-badge.connected {
  background: #dcfce7;
  color: #14532d;
}

:root.dark .status-badge.connected {
  background: rgba(45, 122, 79, 0.15);
  color: #86efac;
}

.integration-actions {
  display: flex;
}

.connect-flow {
  display: flex;
  flex-direction: column;
  gap: var(--to-space-sm);
}

.deep-link-box {
  display: flex;
  flex-direction: column;
  gap: var(--to-space-xs);
  padding: var(--to-space-sm) var(--to-space-md);
  background: var(--to-surface-secondary);
  border: 1px solid var(--to-border);
  border-radius: var(--to-radius-sm);
}

.deep-link {
  font-size: var(--to-text-sm);
  word-break: break-all;
  color: var(--to-brand);
}

.expires-text {
  font-size: var(--to-text-xs);
}
</style>
