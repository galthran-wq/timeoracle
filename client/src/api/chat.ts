import { ApiError, get } from './client'
import type { ChatListResponse, ChatDetail } from '@/types/chat'

export function listChats(limit = 20, offset = 0): Promise<ChatListResponse> {
  return get<ChatListResponse>('/api/agent/chats', {
    limit: String(limit),
    offset: String(offset),
  })
}

export function getChat(chatId: string): Promise<ChatDetail> {
  return get<ChatDetail>(`/api/agent/chats/${chatId}`)
}

export async function chatStream(
  data: { message: string; chat_id?: string },
  callbacks: {
    onText: (text: string) => void
    onDone: (chatId?: string) => void
    onError: (error: string) => void
  },
  signal?: AbortSignal,
): Promise<void> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch('/api/agent/chat', {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
    signal,
  })

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    let message: string
    try {
      const body = await response.json()
      message = body.detail ?? JSON.stringify(body)
    } catch {
      message = response.statusText
    }
    throw new ApiError(response.status, message)
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let eventType = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()!

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        try {
          const parsed = JSON.parse(line.slice(6))
          if (eventType === 'start') {
            callbacks.onDone(parsed.chat_id)
          } else if (eventType === 'text') {
            callbacks.onText(parsed.text)
          } else if (eventType === 'done') {
            callbacks.onDone(parsed.chat_id)
          } else if (eventType === 'error') {
            callbacks.onError(parsed.error)
          }
        } catch {}
        eventType = ''
      }
    }
  }
}
