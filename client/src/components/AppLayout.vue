<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  NLayout,
  NLayoutHeader,
  NLayoutContent,
  NMenu,
  NSpace,
  NButton,
  NSwitch,
  NText,
  NSelect,
} from 'naive-ui'
import type { MenuOption } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import LogoIcon from '@/components/LogoIcon.vue'
import { LOCALE_OPTIONS } from '@/i18n'
import type { SupportedLocale } from '@/i18n'
import { updateSessionConfig } from '@/api/settings'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()

const isLanding = computed(() => route.name === 'landing')
const isFullBleed = computed(() => route.name === 'landing' || route.name === 'login')
const isAuth = computed(() => authStore.isAuthenticated)

const menuKey = computed(() => (route.name as string) ?? 'dashboard')

const menuOptions = computed<MenuOption[]>(() => [
  { label: t('nav.dashboard'), key: 'dashboard' },
  { label: t('nav.activity'), key: 'activity' },
  { label: t('nav.timeline'), key: 'timeline' },
  { label: t('nav.settings'), key: 'settings' },
  { label: t('nav.howItWorks'), key: 'guide' },
])

function onMenuSelect(key: string) {
  router.push({ name: key })
}

function onLogoClick() {
  router.push({ name: isAuth.value ? 'dashboard' : 'landing' })
}

function onLocaleChange(value: SupportedLocale) {
  locale.value = value
  localStorage.setItem('locale', value)
  if (authStore.isAuthenticated) {
    updateSessionConfig({ language: value }).catch(() => {})
  }
}
</script>

<template>
  <NLayout style="height: 100%">
    <NLayoutHeader class="app-header">
      <a v-if="!isLanding" class="brand-group" @click.prevent="onLogoClick">
        <LogoIcon :size="52" />
        <span class="brand">digitalgulag</span>
      </a>

      <NMenu
        v-if="isAuth"
        mode="horizontal"
        :value="menuKey"
        :options="menuOptions"
        style="flex: 1"
        @update:value="onMenuSelect"
      />
      <div v-else class="public-spacer" />

      <NSpace align="center" :size="12" style="white-space: nowrap">
        <a
          v-if="!isAuth"
          class="nav-link"
          @click.prevent="router.push({ name: 'guide', params: { page: 'idea' } })"
        >{{ t('nav.howItWorks') }}</a>
        <NText v-if="isAuth" depth="3" style="font-size: 12px">{{ authStore.user?.email }}</NText>
        <NSwitch :value="themeStore.isDark" size="small" @update:value="themeStore.toggle">
          <template #checked>{{ t('nav.dark') }}</template>
          <template #unchecked>{{ t('nav.light') }}</template>
        </NSwitch>
        <NSelect
          :value="locale"
          :options="LOCALE_OPTIONS"
          size="tiny"
          :consistent-menu-width="false"
          style="width: 60px"
          @update:value="onLocaleChange"
        />
        <a href="https://github.com/galthran-wq/digitalgulag" target="_blank" rel="noopener" class="github-icon" aria-label="GitHub">
          <svg viewBox="0 0 16 16" width="18" height="18" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
        </a>
        <div v-if="isAuth" class="header-divider" />
        <NButton v-if="isAuth" text size="small" @click="authStore.logout">{{ t('nav.logout') }}</NButton>
        <NButton v-if="!isAuth" size="small" type="primary" @click="router.push({ name: 'login' })">{{ t('nav.login') }}</NButton>
      </NSpace>
    </NLayoutHeader>
    <NLayoutContent
      :content-style="isFullBleed ? '' : 'padding: 24px'"
      style="height: calc(100% - 60px)"
    >
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
  text-decoration: none;
  color: inherit;
  cursor: pointer;
}

.brand {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--to-text-primary);
}

.public-spacer {
  flex: 1;
}

.nav-link {
  font-size: 13px;
  font-weight: 500;
  opacity: 0.6;
  cursor: pointer;
  text-decoration: none;
  color: inherit;
  transition: opacity 0.15s;
}

.nav-link:hover {
  opacity: 1;
}

.github-icon {
  display: flex;
  align-items: center;
  color: inherit;
  opacity: 0.4;
  transition: opacity 0.15s;
}

.github-icon:hover {
  opacity: 0.8;
}

.header-divider {
  width: 1px;
  height: 16px;
  background: var(--to-border);
}
</style>
