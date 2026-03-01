import { ref } from 'vue'
import { defineStore } from 'pinia'
import { chatStream } from '@/api/chat'
import type { ChatMessage } from '@/types/chat'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const streaming = ref(false)
  const error = ref<string | null>(null)

  let abortController: AbortController | null = null

  async function sendMessage(content: string, date: string) {
    if (streaming.value) return
    error.value = null

    messages.value.push({
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    })

    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    }
    messages.value.push(assistantMsg)

    streaming.value = true
    abortController = new AbortController()

    try {
      await chatStream(
        { message: content, date },
        {
          onText(text) {
            assistantMsg.content += text
          },
          onDone() {},
          onError(err) {
            error.value = err
          },
        },
        abortController.signal,
      )
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        error.value = e.message ?? 'Chat request failed'
        if (!assistantMsg.content) {
          const idx = messages.value.indexOf(assistantMsg)
          if (idx !== -1) messages.value.splice(idx, 1)
        }
      }
    } finally {
      streaming.value = false
      abortController = null
    }
  }

  function cancelStream() {
    abortController?.abort()
  }

  function clearMessages() {
    messages.value = []
    error.value = null
  }

  return {
    messages,
    streaming,
    error,
    sendMessage,
    cancelStream,
    clearMessages,
  }
})
