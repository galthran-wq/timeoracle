<script setup lang="ts">
import { ref, watch, nextTick, computed, onMounted } from 'vue'
import { NInput, NButton, NText, NScrollbar, NIcon, NSpin } from 'naive-ui'
import { SendOutline, TimeOutline, AddOutline } from '@vicons/ionicons5'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useChatStore } from '@/stores/chat'
import { useTimelineStore } from '@/stores/timeline'

marked.setOptions({ breaks: true, gfm: true })

function renderMarkdown(text: string): string {
  if (!text) return ''
  const html = marked.parse(text, { async: false }) as string
  return DOMPurify.sanitize(html)
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const today = now.toDateString()
  const yesterday = new Date(now.getTime() - 86400000).toDateString()
  const ds = d.toDateString()

  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  if (ds === today) return time
  if (ds === yesterday) return `Yesterday ${time}`
  return `${d.toLocaleDateString([], { month: 'short', day: 'numeric' })} ${time}`
}

const chatStore = useChatStore()
const timelineStore = useTimelineStore()

const inputValue = ref('')
const scrollbarRef = ref<InstanceType<typeof NScrollbar> | null>(null)

const isHistory = computed(() => chatStore.activeView === 'history')

onMounted(() => {
  chatStore.restoreChat()
})

function scrollToBottom(smooth = false) {
  scrollbarRef.value?.scrollTo({ top: 999999, behavior: smooth ? 'smooth' : 'auto' })
}

watch(
  () => chatStore.messages.length,
  async () => {
    await nextTick()
    scrollToBottom(true)
  },
)

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
  await chatStore.sendMessage(text)
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
      <div style="display: flex; align-items: center; gap: 4px">
        <NButton
          v-if="!isHistory && chatStore.activeChatId"
          quaternary
          size="tiny"
          @click="chatStore.newChat()"
          title="New chat"
        >
          <template #icon>
            <NIcon :size="16"><AddOutline /></NIcon>
          </template>
        </NButton>
        <NButton
          quaternary
          size="tiny"
          :type="isHistory ? 'primary' : 'default'"
          @click="isHistory ? chatStore.newChat() : chatStore.showHistory()"
          :title="isHistory ? 'Back to chat' : 'Chat history'"
        >
          <template #icon>
            <NIcon :size="16"><TimeOutline /></NIcon>
          </template>
        </NButton>
      </div>
    </div>

    <template v-if="isHistory">
      <NScrollbar class="chat-messages">
        <NSpin v-if="chatStore.loadingHistory" style="width: 100%; padding: 32px 0" />
        <div v-else-if="!chatStore.chatList.length" class="chat-empty">
          <NText depth="3">No chat history yet.</NText>
        </div>
        <div
          v-else
          v-for="chat in chatStore.chatList"
          :key="chat.id"
          class="history-item"
          @click="chatStore.loadChat(chat.id)"
        >
          <div class="history-item-top">
            <NText depth="3" style="font-size: var(--to-text-sm)">
              {{ formatDate(chat.created_at) }}
            </NText>
          </div>
          <NText
            depth="2"
            style="
              font-size: var(--to-text-base);
              display: -webkit-box;
              -webkit-line-clamp: 2;
              -webkit-box-orient: vertical;
              overflow: hidden;
            "
          >
            {{ chat.preview || 'No messages' }}
          </NText>
        </div>
      </NScrollbar>
    </template>

    <template v-else>
      <NScrollbar ref="scrollbarRef" class="chat-messages">
        <div v-if="!chatStore.messages.length" class="chat-empty">
          <NText depth="3">
            Ask about your day, request fixes to timeline entries, or get explanations.
          </NText>
        </div>

        <div v-for="msg in chatStore.messages" :key="msg.id" class="chat-message" :class="msg.role">
          <div class="chat-bubble" :class="msg.role">
            <template v-if="msg.role === 'assistant'">
              <div class="markdown-body" v-html="renderMarkdown(msg.content)" />
              <span
                v-if="chatStore.streaming && msg === chatStore.messages.at(-1)"
                class="chat-cursor"
              />
            </template>
            <span v-else style="white-space: pre-wrap">{{ msg.content }}</span>
          </div>
        </div>
      </NScrollbar>

      <div v-if="chatStore.error" class="chat-error">
        <NText type="error" style="font-size: 12px">{{ chatStore.error }}</NText>
      </div>

      <div class="chat-input-area" @keydown="handleKeydown">
        <NInput
          v-model:value="inputValue"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 4 }"
          placeholder="Ask about your day..."
          :disabled="chatStore.streaming"
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
    </template>
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

:root.dark .chat-bubble.user {
  color: #1a1a2e;
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
  50% {
    opacity: 0;
  }
}

.history-item {
  padding: var(--to-space-sm) var(--to-space-md);
  border-bottom: 1px solid var(--to-border);
  cursor: pointer;
  transition: background 0.1s;
}

.history-item:hover {
  background: var(--to-surface-secondary);
}

.history-item-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2px;
}

.markdown-body :deep(p) {
  margin: 0 0 0.4em;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.3em 0;
  padding-left: 1.4em;
}

.markdown-body :deep(li) {
  margin: 0.15em 0;
}

.markdown-body :deep(code) {
  font-family: 'Fira Code', monospace;
  font-size: 0.9em;
  padding: 0.15em 0.35em;
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.06);
}

:root.dark .markdown-body :deep(code) {
  background: rgba(255, 255, 255, 0.08);
}

.markdown-body :deep(pre) {
  margin: 0.4em 0;
  padding: 0.6em;
  border-radius: var(--to-radius-sm);
  background: rgba(0, 0, 0, 0.06);
  overflow-x: auto;
}

:root.dark .markdown-body :deep(pre) {
  background: rgba(255, 255, 255, 0.06);
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: none;
}

.markdown-body :deep(strong) {
  font-weight: 600;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  font-size: 1em;
  font-weight: 600;
  margin: 0.5em 0 0.3em;
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
