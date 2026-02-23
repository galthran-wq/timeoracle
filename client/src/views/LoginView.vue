<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NCard, NForm, NFormItem, NInput, NButton, NAlert, NSpace } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/api/client'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function handleSubmit() {
  error.value = ''
  loading.value = true
  try {
    await authStore.login(email.value, password.value)
    router.push({ name: 'dashboard' })
  } catch (e) {
    if (e instanceof ApiError) {
      error.value = e.message
    } else {
      error.value = 'An unexpected error occurred'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="display: flex; align-items: center; justify-content: center; height: 100vh">
    <NCard title="TimeOracle" style="max-width: 400px; width: 100%">
      <NForm @submit.prevent="handleSubmit">
        <NAlert v-if="error" type="error" :title="error" style="margin-bottom: 16px" closable />
        <NFormItem label="Email">
          <NInput v-model:value="email" type="text" placeholder="you@example.com" />
        </NFormItem>
        <NFormItem label="Password">
          <NInput
            v-model:value="password"
            type="password"
            show-password-on="click"
            placeholder="Password"
          />
        </NFormItem>
        <NSpace justify="end">
          <NButton
            type="primary"
            attr-type="submit"
            :loading="loading"
            :disabled="!email || !password"
          >
            Sign In
          </NButton>
        </NSpace>
      </NForm>
    </NCard>
  </div>
</template>
