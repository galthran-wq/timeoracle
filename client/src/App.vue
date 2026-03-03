<script setup lang="ts">
import { computed } from 'vue'
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import type { GlobalThemeOverrides } from 'naive-ui'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import AppLayout from '@/components/AppLayout.vue'

const themeStore = useThemeStore()
const authStore = useAuthStore()

const fontFamily = "'Inter Variable', 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

const themeOverrides = computed<GlobalThemeOverrides>(() => {
  if (themeStore.isDark) {
    return {
      common: {
        primaryColor: '#e8e6f0',
        primaryColorHover: '#ffffff',
        primaryColorPressed: '#c8c6d0',
        primaryColorSuppl: '#d5d3e0',
        borderRadius: '6px',
        borderRadiusSmall: '4px',
        fontFamily,
      },
      Card: {
        borderRadius: '10px',
      },
      Button: {
        textColorPrimary: '#1a1a2e',
      },
    }
  }
  return {
    common: {
      primaryColor: '#1a1a2e',
      primaryColorHover: '#2d2d4a',
      primaryColorPressed: '#111122',
      primaryColorSuppl: '#3a3a5a',
      borderRadius: '6px',
      borderRadiusSmall: '4px',
      fontFamily,
    },
    Card: {
      borderRadius: '10px',
    },
  }
})
</script>

<template>
  <NConfigProvider :theme="themeStore.theme" :theme-overrides="themeOverrides">
    <NMessageProvider>
      <AppLayout v-if="authStore.isAuthenticated" />
      <router-view v-else v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" />
        </Transition>
      </router-view>
    </NMessageProvider>
  </NConfigProvider>
</template>
