export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

export interface ChatSummary {
  id: string
  trigger: string
  created_at: string
  total_input_tokens: number
  total_output_tokens: number
  preview: string
}

export interface ChatMessageItem {
  role: string
  content: string
}

export interface ChatDetail extends ChatSummary {
  messages: ChatMessageItem[]
}

export interface ChatListResponse {
  chats: ChatSummary[]
  total_count: number
}
