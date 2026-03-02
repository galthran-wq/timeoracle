import { ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { chatStream, listChats, getChat } from '@/api/chat'
import type { ChatMessage, ChatSummary } from '@/types/chat'

let msgSeq = 0
const uid = () => `msg-${Date.now()}-${++msgSeq}`

const ACTIVE_CHAT_KEY = 'activeChatId'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const streaming = ref(false)
  const error = ref<string | null>(null)

  const activeChatId = ref<string | null>(localStorage.getItem(ACTIVE_CHAT_KEY))

  watch(activeChatId, (id) => {
    if (id) localStorage.setItem(ACTIVE_CHAT_KEY, id)
    else localStorage.removeItem(ACTIVE_CHAT_KEY)
  })

  const activeView = ref<'chat' | 'history'>('chat')
  const chatList = ref<ChatSummary[]>([])
  const chatListTotal = ref(0)
  const loadingHistory = ref(false)

  let abortController: AbortController | null = null

  async function sendMessage(content: string) {
    if (streaming.value) return
    error.value = null

    messages.value.push({
      id: uid(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    })

    messages.value.push({
      id: uid(),
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    })
    const assistantMsg = messages.value[messages.value.length - 1]

    streaming.value = true
    abortController = new AbortController()

    try {
      await chatStream(
        { message: content, chat_id: activeChatId.value ?? undefined },
        {
          onText(text) {
            assistantMsg.content += text
          },
          onDone(chatId) {
            if (chatId) activeChatId.value = chatId
          },
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
          messages.value.splice(messages.value.length - 1, 1)
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
    activeChatId.value = null
  }

  async function fetchHistory() {
    loadingHistory.value = true
    try {
      const res = await listChats(50, 0)
      chatList.value = res.chats
      chatListTotal.value = res.total_count
    } catch (e: any) {
      error.value = e.message ?? 'Failed to load history'
    } finally {
      loadingHistory.value = false
    }
  }

  async function loadChat(chatId: string): Promise<boolean> {
    loadingHistory.value = true
    try {
      const detail = await getChat(chatId)
      messages.value = detail.messages.map((m) => ({
        id: uid(),
        role: m.role as 'user' | 'assistant',
        content: m.content,
        timestamp: detail.created_at,
      }))
      activeChatId.value = chatId
      activeView.value = 'chat'
      return true
    } catch (e: any) {
      error.value = e.message ?? 'Failed to load chat'
      return false
    } finally {
      loadingHistory.value = false
    }
  }

  function newChat() {
    clearMessages()
    activeView.value = 'chat'
  }

  function showHistory() {
    activeView.value = 'history'
    fetchHistory()
  }

  async function restoreChat() {
    if (activeChatId.value && !messages.value.length) {
      const restored = await loadChat(activeChatId.value)
      if (!restored) activeChatId.value = null
    }
  }

  return {
    messages,
    streaming,
    error,
    activeView,
    chatList,
    chatListTotal,
    loadingHistory,
    activeChatId,
    sendMessage,
    cancelStream,
    clearMessages,
    fetchHistory,
    loadChat,
    newChat,
    showHistory,
    restoreChat,
  }
})
