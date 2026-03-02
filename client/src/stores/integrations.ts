import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import {
  getIntegrations,
  connectTelegram,
  disconnectTelegram,
} from '@/api/integrations'
import type { IntegrationStatus } from '@/types/integrations'

export const useIntegrationsStore = defineStore('integrations', () => {
  const integrations = ref<IntegrationStatus[]>([])
  const loading = ref(false)

  const telegram = computed(
    () => integrations.value.find((i) => i.provider === 'telegram') ?? null,
  )

  async function load() {
    loading.value = true
    try {
      const res = await getIntegrations()
      integrations.value = res.integrations
    } finally {
      loading.value = false
    }
  }

  async function startTelegramConnect() {
    return await connectTelegram()
  }

  async function telegramDisconnect() {
    const res = await disconnectTelegram()
    if (res.success) {
      await load()
    }
    return res
  }

  return { integrations, loading, telegram, load, startTelegramConnect, telegramDisconnect }
})
