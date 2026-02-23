<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NLayout,
  NLayoutHeader,
  NLayoutContent,
  NMenu,
  NSpace,
  NButton,
  NSwitch,
  NText,
} from 'naive-ui'
import type { MenuOption } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()

const menuKey = computed(() => (route.name as string) ?? 'dashboard')

const menuOptions: MenuOption[] = [
  { label: 'Dashboard', key: 'dashboard' },
  { label: 'Activity', key: 'activity' },
  { label: 'Timeline', key: 'timeline' },
]

function onMenuSelect(key: string) {
  router.push({ name: key })
}
</script>

<template>
  <NLayout style="height: 100%">
    <NLayoutHeader bordered style="padding: 0 24px; display: flex; align-items: center; gap: 16px">
      <NText strong style="font-size: 18px; white-space: nowrap; margin-right: 8px">
        TimeOracle
      </NText>
      <NMenu
        mode="horizontal"
        :value="menuKey"
        :options="menuOptions"
        style="flex: 1"
        @update:value="onMenuSelect"
      />
      <NSpace align="center" :size="12" style="white-space: nowrap">
        <NText depth="3" style="font-size: 13px">{{ authStore.user?.email }}</NText>
        <NSwitch :value="themeStore.isDark" size="small" @update:value="themeStore.toggle">
          <template #checked>Dark</template>
          <template #unchecked>Light</template>
        </NSwitch>
        <NButton text size="small" @click="authStore.logout">Logout</NButton>
      </NSpace>
    </NLayoutHeader>
    <NLayoutContent content-style="padding: 24px" style="height: calc(100% - 56px)">
      <slot />
    </NLayoutContent>
  </NLayout>
</template>
