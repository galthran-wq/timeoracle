import 'temporal-polyfill/global'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@fontsource-variable/inter'
import 'vfonts/FiraCode.css'

import App from './App.vue'
import router from './router'
import i18n from './i18n'
import { useAuthStore } from './stores/auth'
import './assets/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(i18n)

const authStore = useAuthStore()
authStore.init().then(() => {
  const lang = authStore.user?.session_config?.language
  if (lang && (lang === 'en' || lang === 'ru')) {
    i18n.global.locale.value = lang
    localStorage.setItem('locale', lang)
  }
  app.use(router)
  app.mount('#app')
})
