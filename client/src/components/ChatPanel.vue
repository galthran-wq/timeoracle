<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { NInput, NButton, NText, NScrollbar, NIcon } from 'naive-ui'
import { SendOutline } from '@vicons/ionicons5'
import { useChatStore } from '@/stores/chat'
import { useTimelineStore } from '@/stores/timeline'

const chatStore = useChatStore()
const timelineStore = useTimelineStore()

const inputValue = ref('')
const scrollbarRef = ref<InstanceType<typeof NScrollbar> | null>(null)

function scrollToBottom(smooth = false) {
  scrollbarRef.value?.scrollTo({ top: 999999, behavior: smooth ? 'smooth' : 'auto' })
}

watch(() => chatStore.messages.length, async () => {
  await nextTick()
  scrollToBottom(true)
})

watch(
  () => chatStore.messages.at(-1)?.content,
  async () => {
    await nextTick()
    scrollToBottom()
  },
)

async function handleSend() {
  const text = inputValue.value.trim()
  if (!text || chatStore.streaming) return
  inputValue.value = ''
  await chatStore.sendMessage(text, timelineStore.selectedDate)
  await timelineStore.fetchEntries()
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}
</script>

<template>
  <div class="chat-panel">
    <div class="chat-header">
      <NText strong>AI Agent</NText>
      <NText depth="3" style="font-size: 12px">{{ timelineStore.selectedDate }}</NText>
    </div>

    <NScrollbar ref="scrollbarRef" class="chat-messages">
      <div v-if="!chatStore.messages.length" class="chat-empty">
        <NText depth="3">
          Ask about your day, request fixes to timeline entries, or get explanations.
        </NText>
      </div>

      <div
        v-for="msg in chatStore.messages"
        :key="msg.id"
        class="chat-message"
        :class="msg.role"
      >
        <div class="chat-bubble" :class="msg.role">
          <span style="white-space: pre-wrap">{{ msg.content }}</span>
          <span
            v-if="chatStore.streaming && msg === chatStore.messages.at(-1) && msg.role === 'assistant'"
            class="chat-cursor"
          />
        </div>
      </div>
    </NScrollbar>

    <div v-if="chatStore.error" class="chat-error">
      <NText type="error" style="font-size: 12px">{{ chatStore.error }}</NText>
    </div>

    <div class="chat-input-area">
      <NInput
        v-model:value="inputValue"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 4 }"
        placeholder="Ask about your day..."
        :disabled="chatStore.streaming"
        @keydown="handleKeydown"
      />
      <NButton
        type="primary"
        :disabled="!inputValue.trim() || chatStore.streaming"
        :loading="chatStore.streaming"
        @click="handleSend"
      >
        <template #icon>
          <NIcon><SendOutline /></NIcon>
        </template>
      </NButton>
    </div>
  </div>
</template>

<style scoped>
.chat-panel {
  width: 360px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--to-border);
  background: var(--to-surface);
  height: 100%;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--to-space-md);
  border-bottom: 1px solid var(--to-border);
}

.chat-messages {
  flex: 1;
  min-height: 0;
  padding: var(--to-space-md);
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--to-space-md);
  padding: var(--to-space-xl) var(--to-space-md);
  text-align: center;
}

.chat-message {
  margin-bottom: var(--to-space-md);
  display: flex;
}

.chat-message.user {
  justify-content: flex-end;
}

.chat-message.assistant {
  justify-content: flex-start;
}

.chat-bubble {
  max-width: 85%;
  padding: var(--to-space-sm) var(--to-space-md);
  border-radius: var(--to-radius-lg);
  font-size: var(--to-text-base);
  line-height: 1.5;
  word-wrap: break-word;
}

.chat-bubble.user {
  background: var(--to-brand);
  color: white;
  border-bottom-right-radius: var(--to-radius-sm);
}

.chat-bubble.assistant {
  background: var(--to-surface-secondary);
  border: 1px solid var(--to-border);
  border-bottom-left-radius: var(--to-radius-sm);
}

.chat-cursor {
  display: inline-block;
  width: 6px;
  height: 14px;
  background: var(--to-text-secondary);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}

.chat-error {
  padding: var(--to-space-xs) var(--to-space-md);
}

.chat-input-area {
  display: flex;
  align-items: flex-end;
  gap: var(--to-space-sm);
  padding: var(--to-space-md);
  border-top: 1px solid var(--to-border);
}
</style>
