import { ApiError, apiFetch, apiRequest } from "@/shared/api/client";

import type { ChatEvent, Conversation, ConversationSummary } from "./types";

type ChatEventHandler = (event: ChatEvent) => void | Promise<void>;

export function listConversations(
  signal?: AbortSignal,
): Promise<ConversationSummary[]> {
  return apiRequest<ConversationSummary[]>("/api/v1/conversations", { signal });
}

export function createConversation(): Promise<Conversation> {
  return apiRequest<Conversation>("/api/v1/conversations", { method: "POST" });
}

export function getConversation(
  conversationId: string,
  signal?: AbortSignal,
): Promise<Conversation> {
  return apiRequest<Conversation>(
    `/api/v1/conversations/${conversationId}`,
    { signal },
  );
}

export async function streamChatMessage(
  conversationId: string,
  content: string,
  onEvent: ChatEventHandler,
  signal?: AbortSignal,
): Promise<void> {
  const response = await apiFetch(`/api/v1/chat/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content }),
    signal,
  });

  if (!response.body) {
    throw new Error("浏览器未提供可读取的事件流。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let receivedFinal = false;

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    buffer = buffer.replaceAll("\r\n", "\n");

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = parseEvent(block);

      if (event) {
        await onEvent(event);
        if (event.type === "error") {
          throw new Error(event.content);
        }
        if (event.type === "final") {
          receivedFinal = true;
        }
      }

      boundary = buffer.indexOf("\n\n");
    }

    if (done) {
      break;
    }
  }

  const trailingEvent = parseEvent(buffer);
  if (trailingEvent) {
    await onEvent(trailingEvent);
    if (trailingEvent.type === "error") {
      throw new Error(trailingEvent.content);
    }
    if (trailingEvent.type === "final") {
      receivedFinal = true;
    }
  }

  if (!receivedFinal) {
    throw new Error("事件流未正常返回最终回答，请重试。");
  }
}

function parseEvent(block: string): ChatEvent | null {
  const data = block
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");

  if (!data) {
    return null;
  }

  const value: unknown = JSON.parse(data);
  if (!isChatEvent(value)) {
    throw new ApiError("服务端返回了无法识别的事件。", 502);
  }
  return value;
}

function isChatEvent(value: unknown): value is ChatEvent {
  if (!value || typeof value !== "object") {
    return false;
  }

  const event = value as Partial<ChatEvent>;
  return (
    typeof event.type === "string" &&
    ["token", "tool_start", "tool_end", "final", "error"].includes(
      event.type,
    ) &&
    typeof event.run_id === "string" &&
    typeof event.conversation_id === "string" &&
    typeof event.sequence === "number" &&
    typeof event.content === "string"
  );
}
