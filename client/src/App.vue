<script setup lang="ts">
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import type { GlobalThemeOverrides } from 'naive-ui'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import AppLayout from '@/components/AppLayout.vue'

const themeStore = useThemeStore()
const authStore = useAuthStore()

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#3B82F6',
    primaryColorHover: '#2563EB',
    primaryColorPressed: '#1D4ED8',
    primaryColorSuppl: '#60A5FA',
    borderRadius: '6px',
    borderRadiusSmall: '4px',
  },
  Card: {
    borderRadius: '10px',
  },
}
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
