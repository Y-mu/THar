export type MessageRole = "user" | "assistant";

export type ChatMessage = {
  role: MessageRole;
  content: string;
  created_at: string;
};

export type ConversationSummary = {
  conversation_id: string;
  created_at: string;
  updated_at: string;
};

export type Conversation = ConversationSummary & {
  messages: ChatMessage[];
};

export type ChatEventType =
  | "token"
  | "tool_start"
  | "tool_end"
  | "final"
  | "error";

export type ChatEvent = {
  type: ChatEventType;
  run_id: string;
  conversation_id: string;
  sequence: number;
  content: string;
  name?: string;
  reason?: string;
};

export type DisplayMessage = ChatMessage & {
  client_id: string;
  streaming?: boolean;
};
