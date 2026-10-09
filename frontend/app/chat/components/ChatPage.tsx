"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  type FormEvent,
  type KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import { ApiError } from "@/shared/api/client";

import {
  createConversation,
  getConversation,
  listConversations,
  streamChatMessage,
} from "../chat";
import type {
  ChatEvent,
  ChatMessage,
  ConversationSummary,
  DisplayMessage,
} from "../types";

const conversationDateFormatter = new Intl.DateTimeFormat("zh-CN", {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const messageTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  hour: "2-digit",
  minute: "2-digit",
});

export function ChatPage() {
  const router = useRouter();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [toolStatus, setToolStatus] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const loadRequestRef = useRef(0);
  const streamControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadInitialConversation() {
      try {
        const items = await listConversations(controller.signal);
        setConversations(items);

        const firstConversation = items[0];
        if (firstConversation) {
          const conversation = await getConversation(
            firstConversation.conversation_id,
            controller.signal,
          );
          setActiveConversationId(conversation.conversation_id);
          setMessages(toDisplayMessages(conversation.messages));
        }
      } catch (cause) {
        if (controller.signal.aborted) {
          return;
        }
        if (!redirectWhenUnauthorized(cause, router.replace)) {
          setError(errorMessage(cause));
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    void loadInitialConversation();
    return () => controller.abort();
  }, [router]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages, toolStatus]);

  useEffect(() => {
    return () => streamControllerRef.current?.abort();
  }, []);

  async function handleSelectConversation(conversationId: string) {
    if (isSending || conversationId === activeConversationId) {
      setIsSidebarOpen(false);
      return;
    }

    const requestId = ++loadRequestRef.current;
    setError("");
    setIsLoadingMessages(true);
    setActiveConversationId(conversationId);
    setIsSidebarOpen(false);

    try {
      const conversation = await getConversation(conversationId);
      if (loadRequestRef.current === requestId) {
        setMessages(toDisplayMessages(conversation.messages));
      }
    } catch (cause) {
      if (!redirectWhenUnauthorized(cause, router.replace)) {
        setError(errorMessage(cause));
      }
    } finally {
      if (loadRequestRef.current === requestId) {
        setIsLoadingMessages(false);
      }
    }
  }

  async function handleCreateConversation() {
    if (isSending || isCreating) {
      return;
    }

    setError("");
    setIsCreating(true);
    try {
      const conversation = await createConversation();
      setConversations((current) => [
        toConversationSummary(conversation),
        ...current,
      ]);
      setActiveConversationId(conversation.conversation_id);
      setMessages([]);
      setIsSidebarOpen(false);
    } catch (cause) {
      if (!redirectWhenUnauthorized(cause, router.replace)) {
        setError(errorMessage(cause));
      }
    } finally {
      setIsCreating(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    const conversationId = activeConversationId;

    if (!content || !conversationId || isSending) {
      return;
    }

    const sentAt = new Date().toISOString();
    const userMessageId = `user-${Date.now()}`;
    const assistantMessageId = `assistant-${Date.now()}`;
    const controller = new AbortController();
    streamControllerRef.current = controller;

    setDraft("");
    setError("");
    setToolStatus(null);
    setIsSending(true);
    setMessages((current) => [
      ...current,
      {
        client_id: userMessageId,
        role: "user",
        content,
        created_at: sentAt,
      },
      {
        client_id: assistantMessageId,
        role: "assistant",
        content: "",
        created_at: sentAt,
        streaming: true,
      },
    ]);

    try {
      await streamChatMessage(
        conversationId,
        content,
        (chatEvent) => {
          applyChatEvent(
            chatEvent,
            assistantMessageId,
            setMessages,
            setToolStatus,
          );
        },
        controller.signal,
      );

      try {
        setConversations(await listConversations());
      } catch {
        // 回答已经完成，刷新会话排序失败不影响当前消息。
      }
    } catch (cause) {
      if (controller.signal.aborted) {
        return;
      }

      if (redirectWhenUnauthorized(cause, router.replace)) {
        return;
      }

      setError(errorMessage(cause));
      setDraft(content);
      try {
        const conversation = await getConversation(conversationId);
        setMessages(toDisplayMessages(conversation.messages));
      } catch {
        setMessages((current) =>
          current.filter(
            (message) =>
              message.client_id !== userMessageId &&
              message.client_id !== assistantMessageId,
          ),
        );
      }
    } finally {
      if (streamControllerRef.current === controller) {
        streamControllerRef.current = null;
      }
      setToolStatus(null);
      setIsSending(false);
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  const activeConversation = conversations.find(
    (conversation) =>
      conversation.conversation_id === activeConversationId,
  );

  return (
    <main className="flex h-dvh min-h-0 overflow-hidden bg-background text-foreground">
      {isSidebarOpen ? (
        <button
          type="button"
          className="fixed inset-0 z-30 cursor-pointer bg-black/70 md:hidden"
          aria-label="关闭会话列表"
          onClick={() => setIsSidebarOpen(false)}
        />
      ) : null}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[min(86vw,20rem)] shrink-0 flex-col border-r border-border bg-surface transition-transform duration-200 md:visible md:static md:w-72 md:translate-x-0 ${isSidebarOpen ? "visible translate-x-0" : "invisible -translate-x-full"}`}
        aria-label="会话列表"
      >
        <div className="flex min-h-16 items-center justify-between border-b border-border px-4">
          <Link
            href="/"
            className="flex items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <span className="grid size-9 place-items-center rounded-xl border border-accent/30 bg-accent/10 text-sm font-bold text-accent">
              T
            </span>
            <span className="font-semibold tracking-tight">THar</span>
          </Link>
          <button
            type="button"
            className="grid size-11 cursor-pointer place-items-center rounded-xl text-muted transition hover:bg-background hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent md:hidden"
            aria-label="关闭会话列表"
            onClick={() => setIsSidebarOpen(false)}
          >
            <CloseIcon />
          </button>
        </div>

        <div className="p-3">
          <button
            type="button"
            onClick={handleCreateConversation}
            disabled={isCreating || isSending}
            className="flex min-h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-accent px-4 text-sm font-semibold text-accent-foreground transition hover:bg-accent-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:opacity-60"
          >
            <PlusIcon />
            {isCreating ? "创建中…" : "新建会话"}
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
          <p className="px-2 pb-2 pt-3 font-mono text-xs font-semibold uppercase tracking-[0.16em] text-muted">
            Conversations
          </p>

          {isLoading ? (
            <p className="px-2 py-4 text-sm text-muted">正在加载会话…</p>
          ) : null}

          {!isLoading && conversations.length === 0 ? (
            <p className="px-2 py-4 text-sm leading-6 text-muted">
              还没有会话，点击上方按钮开始。
            </p>
          ) : null}

          <div className="space-y-1">
            {conversations.map((conversation) => {
              const isActive =
                conversation.conversation_id === activeConversationId;
              return (
                <button
                  key={conversation.conversation_id}
                  type="button"
                  onClick={() =>
                    handleSelectConversation(conversation.conversation_id)
                  }
                  disabled={isSending}
                  aria-current={isActive ? "page" : undefined}
                  className={`w-full cursor-pointer rounded-xl border px-3 py-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-60 ${isActive ? "border-accent/25 bg-accent/10" : "border-transparent hover:border-border hover:bg-background/70"}`}
                >
                  <span className="block truncate text-sm font-medium text-foreground">
                    会话 {conversation.conversation_id.slice(0, 8)}
                  </span>
                  <span className="mt-1 block text-xs text-muted">
                    {formatDate(
                      conversation.updated_at,
                      conversationDateFormatter,
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="border-t border-border p-3">
          <Link
            href="/"
            className="flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium text-muted transition hover:bg-background hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <HomeIcon />
            返回主页
          </Link>
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex min-h-16 shrink-0 items-center justify-between gap-4 border-b border-border px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              className="grid size-11 shrink-0 cursor-pointer place-items-center rounded-xl text-muted transition hover:bg-surface hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent md:hidden"
              aria-label="打开会话列表"
              onClick={() => setIsSidebarOpen(true)}
            >
              <MenuIcon />
            </button>
            <div className="min-w-0">
              <h1 className="truncate text-sm font-semibold sm:text-base">
                {activeConversation
                  ? `会话 ${activeConversation.conversation_id.slice(0, 8)}`
                  : "Agent 对话"}
              </h1>
              <p className="mt-0.5 hidden text-xs text-muted sm:block">
                所有请求都会先经过意图路由
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs text-muted">
            <span className="size-2 rounded-full bg-accent" aria-hidden="true" />
            已连接
          </div>
        </header>

        {error ? (
          <div
            role="alert"
            className="mx-4 mt-4 flex items-start justify-between gap-4 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm leading-6 text-danger sm:mx-6"
          >
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError("")}
              className="grid size-11 shrink-0 cursor-pointer place-items-center rounded-lg transition hover:bg-danger/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger"
              aria-label="关闭错误提示"
            >
              <CloseIcon />
            </button>
          </div>
        ) : null}

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex min-h-full w-full max-w-4xl flex-col px-4 py-6 sm:px-8 sm:py-10">
            {isLoading || isLoadingMessages ? (
              <div className="flex flex-1 items-center justify-center text-sm text-muted">
                正在加载消息…
              </div>
            ) : null}

            {!isLoading && !isLoadingMessages && !activeConversationId ? (
              <div className="flex flex-1 flex-col items-center justify-center py-16 text-center">
                <div className="grid size-14 place-items-center rounded-2xl border border-accent/25 bg-accent/10 text-accent">
                  <MessageIcon />
                </div>
                <h2 className="mt-6 text-2xl font-semibold tracking-tight">
                  开始一次可信对话
                </h2>
                <p className="mt-3 max-w-md text-sm leading-7 text-muted">
                  创建对话后发送消息。THar 会先判断意图和置信度，再决定是否运行 Agent。
                </p>
                <button
                  type="button"
                  onClick={handleCreateConversation}
                  disabled={isCreating}
                  className="mt-7 flex min-h-11 cursor-pointer items-center gap-2 rounded-xl bg-accent px-5 text-sm font-semibold text-accent-foreground transition hover:bg-accent-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <PlusIcon />
                  {isCreating ? "创建中…" : "创建第一个会话"}
                </button>
              </div>
            ) : null}

            {!isLoading && !isLoadingMessages && activeConversationId ? (
              messages.length === 0 ? (
                <div className="flex flex-1 flex-col items-center justify-center py-16 text-center">
                  <div className="grid size-14 place-items-center rounded-2xl border border-accent/25 bg-accent/10 text-accent">
                    <MessageIcon />
                  </div>
                  <h2 className="mt-6 text-2xl font-semibold tracking-tight">
                    有什么想聊的？
                  </h2>
                  <p className="mt-3 max-w-md text-sm leading-7 text-muted">
                    输入一个具体问题。若意图不明确，Agent 会先请你补充信息。
                  </p>
                </div>
              ) : (
                <div className="space-y-7">
                  {messages.map((message) => (
                    <MessageItem key={message.client_id} message={message} />
                  ))}
                  {toolStatus ? (
                    <div
                      className="ml-12 flex items-center gap-2 text-xs text-muted"
                      role="status"
                      aria-live="polite"
                    >
                      <span
                        className="size-2 rounded-full bg-accent motion-safe:animate-pulse"
                        aria-hidden="true"
                      />
                      {toolStatus}
                    </div>
                  ) : null}
                </div>
              )
            ) : null}
            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className="shrink-0 border-t border-border bg-background/95 px-4 py-4 sm:px-6">
          <form
            onSubmit={handleSubmit}
            className="mx-auto w-full max-w-4xl"
          >
            <label htmlFor="chat-message" className="sr-only">
              输入消息
            </label>
            <div className="flex items-end gap-2 rounded-2xl border border-border bg-surface p-2 transition focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/10">
              <textarea
                id="chat-message"
                name="message"
                rows={2}
                maxLength={20_000}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                disabled={!activeConversationId || isSending}
                placeholder={
                  activeConversationId ? "输入消息…" : "请先创建一个会话"
                }
                className="max-h-40 min-h-12 flex-1 resize-none bg-transparent px-3 py-3 text-base leading-6 text-foreground outline-none placeholder:text-muted disabled:cursor-not-allowed disabled:opacity-60"
              />
              <button
                type="submit"
                disabled={!activeConversationId || !draft.trim() || isSending}
                className="grid size-12 shrink-0 cursor-pointer place-items-center rounded-xl bg-accent text-accent-foreground transition hover:bg-accent-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:opacity-40"
                aria-label={isSending ? "正在发送" : "发送消息"}
              >
                <SendIcon />
              </button>
            </div>
            <p className="mt-2 text-center text-xs text-muted">
              Enter 发送 · Shift + Enter 换行 · 回答可能存在错误，请核验重要信息
            </p>
          </form>
        </div>
      </section>
    </main>
  );
}

function MessageItem({ message }: { message: DisplayMessage }) {
  if (message.role === "user") {
    return (
      <article className="flex justify-end">
        <div className="max-w-[88%] rounded-2xl rounded-br-md bg-accent px-4 py-3 text-accent-foreground sm:max-w-[75%]">
          <p className="whitespace-pre-wrap break-words text-sm leading-7 sm:text-base">
            {message.content}
          </p>
          <p className="mt-1 text-right text-xs opacity-65">
            {formatDate(message.created_at, messageTimeFormatter)}
          </p>
        </div>
      </article>
    );
  }

  return (
    <article className="flex items-start gap-3">
      <div className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-xl border border-accent/25 bg-accent/10 text-xs font-bold text-accent">
        T
      </div>
      <div className="min-w-0 max-w-[calc(100%_-_3rem)]">
        {message.streaming && !message.content ? (
          <div className="flex min-h-10 items-center gap-1.5" role="status">
            <span className="size-1.5 rounded-full bg-muted motion-safe:animate-pulse" />
            <span className="size-1.5 rounded-full bg-muted motion-safe:animate-pulse [animation-delay:120ms]" />
            <span className="size-1.5 rounded-full bg-muted motion-safe:animate-pulse [animation-delay:240ms]" />
            <span className="sr-only">Agent 正在思考</span>
          </div>
        ) : (
          <p className="whitespace-pre-wrap break-words text-sm leading-7 text-foreground sm:text-base">
            {message.content}
            {message.streaming ? (
              <span
                className="ml-1 inline-block h-4 w-0.5 bg-accent align-middle motion-safe:animate-pulse"
                aria-hidden="true"
              />
            ) : null}
          </p>
        )}
        <p className="mt-1 text-xs text-muted">
          {formatDate(message.created_at, messageTimeFormatter)}
        </p>
      </div>
    </article>
  );
}

function applyChatEvent(
  event: ChatEvent,
  assistantMessageId: string,
  setMessages: React.Dispatch<React.SetStateAction<DisplayMessage[]>>,
  setToolStatus: React.Dispatch<React.SetStateAction<string | null>>,
) {
  if (event.type === "tool_start") {
    setToolStatus(`正在使用工具：${event.name ?? "未命名工具"}`);
    return;
  }

  if (event.type === "tool_end") {
    setToolStatus(null);
    return;
  }

  if (event.type !== "token" && event.type !== "final") {
    return;
  }

  setMessages((current) =>
    current.map((message) => {
      if (message.client_id !== assistantMessageId) {
        return message;
      }
      return {
        ...message,
        content:
          event.type === "final"
            ? event.content
            : `${message.content}${event.content}`,
        streaming: event.type !== "final",
      };
    }),
  );
}

function toDisplayMessages(messages: ChatMessage[]): DisplayMessage[] {
  return messages.map((message, index) => ({
    ...message,
    client_id: `${message.created_at}-${message.role}-${index}`,
  }));
}

function toConversationSummary(
  conversation: ConversationSummary,
): ConversationSummary {
  return {
    conversation_id: conversation.conversation_id,
    created_at: conversation.created_at,
    updated_at: conversation.updated_at,
  };
}

function redirectWhenUnauthorized(
  cause: unknown,
  replace: (href: string) => void,
): boolean {
  if (cause instanceof ApiError && cause.status === 401) {
    replace("/login");
    return true;
  }
  return false;
}

function errorMessage(cause: unknown): string {
  return cause instanceof Error
    ? cause.message
    : "请求失败，请确认服务端已经启动后重试。";
}

function formatDate(value: string, formatter: Intl.DateTimeFormat): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "时间未知" : formatter.format(date);
}

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-5" fill="none" aria-hidden="true">
      <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-5" fill="none" aria-hidden="true">
      <path d="m7 7 10 10M17 7 7 17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-4" fill="none" aria-hidden="true">
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-5" fill="none" aria-hidden="true">
      <path d="m4 10 8-6 8 6v9a1 1 0 0 1-1 1h-5v-6h-4v6H5a1 1 0 0 1-1-1v-9Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

function MessageIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" fill="none" aria-hidden="true">
      <path d="M5 5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H9l-5 3v-3.5A2 2 0 0 1 3 15V7a2 2 0 0 1 2-2Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-5" fill="none" aria-hidden="true">
      <path d="m5 12 14-7-4.5 14-3-5.5L5 12Zm6.5 1.5L19 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
