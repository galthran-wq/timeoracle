import 'temporal-polyfill/global'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@fontsource-variable/inter'
import 'vfonts/FiraCode.css'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import './assets/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)

const authStore = useAuthStore()
authStore.init().then(() => {
  app.use(router)
  app.mount('#app')
})
