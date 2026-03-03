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
import LogoIcon from '@/components/LogoIcon.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()

const menuKey = computed(() => (route.name as string) ?? 'dashboard')

const menuOptions: MenuOption[] = [
  { label: 'Dashboard', key: 'dashboard' },
  { label: 'Activity', key: 'activity' },
  { label: 'Timeline', key: 'timeline' },
  { label: 'Settings', key: 'settings' },
]

function onMenuSelect(key: string) {
  router.push({ name: key })
}
</script>

<template>
  <NLayout style="height: 100%">
    <NLayoutHeader class="app-header">
      <div class="brand-group">
        <LogoIcon :size="52" />
        <span class="brand">digitalgulag</span>
      </div>
      <NMenu
        mode="horizontal"
        :value="menuKey"
        :options="menuOptions"
        style="flex: 1"
        @update:value="onMenuSelect"
      />
      <NSpace align="center" :size="12" style="white-space: nowrap">
        <NText depth="3" style="font-size: 12px">{{ authStore.user?.email }}</NText>
        <NSwitch :value="themeStore.isDark" size="small" @update:value="themeStore.toggle">
          <template #checked>Dark</template>
          <template #unchecked>Light</template>
        </NSwitch>
        <div class="header-divider" />
        <NButton text size="small" @click="authStore.logout">Logout</NButton>
      </NSpace>
    </NLayoutHeader>
    <NLayoutContent content-style="padding: 24px" style="height: calc(100% - 60px)">
      <router-view v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" />
        </Transition>
      </router-view>
    </NLayoutContent>
  </NLayout>
</template>

<style scoped>
.app-header {
  padding: 0 32px;
  height: 60px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 1px 0 var(--to-border);
}

.brand-group {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
  margin-right: 8px;
}

.brand {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--to-text-primary);
}

.header-divider {
  width: 1px;
  height: 16px;
  background: var(--to-border);
}
</style>
