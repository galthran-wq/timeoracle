<script setup lang="ts">
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import AppLayout from '@/components/AppLayout.vue'

const themeStore = useThemeStore()
const authStore = useAuthStore()
</script>

<template>
  <NConfigProvider :theme="themeStore.theme">
    <NMessageProvider>
      <AppLayout v-if="authStore.isAuthenticated">
        <router-view />
      </AppLayout>
      <router-view v-else />
    </NMessageProvider>
  </NConfigProvider>
</template>
