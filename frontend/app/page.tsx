"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError, apiRequest } from "@/shared/api/client";

type CurrentUser = {
  user_id: number;
  username: string;
  identity_level: "user" | "admin";
};

type AuthState = "loading" | "guest" | "authenticated" | "unavailable";

const principles = [
  {
    number: "01",
    title: "可信意图路由",
    description: "分类不可用、意图未知或置信度不足时故障关闭，先澄清再执行。",
  },
  {
    number: "02",
    title: "最小工具权限",
    description: "Agent 只获得当前意图所需工具，通用对话不携带业务能力。",
  },
  {
    number: "03",
    title: "隔离会话上下文",
    description: "每个用户拥有独立 Conversation，仅持久化用户消息和最终回答。",
  },
];

export default function Home() {
  const [authState, setAuthState] = useState<AuthState>("loading");
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    async function loadCurrentUser() {
      try {
        const currentUser = await apiRequest<CurrentUser>("/api/v1/users/me", {
          signal: controller.signal,
        });
        setUser(currentUser);
        setAuthState("authenticated");
      } catch (cause) {
        if (controller.signal.aborted) {
          return;
        }

        if (cause instanceof ApiError && cause.status === 401) {
          setAuthState("guest");
          return;
        }

        setAuthState("unavailable");
      }
    }

    void loadCurrentUser();
    return () => controller.abort();
  }, []);

  async function handleLogout() {
    setIsLoggingOut(true);
    try {
      await apiRequest<void>("/api/v1/users/logout", { method: "POST" });
      setUser(null);
      setAuthState("guest");
    } catch {
      setAuthState("unavailable");
    } finally {
      setIsLoggingOut(false);
    }
  }

  return (
    <main className="relative min-h-dvh overflow-hidden bg-background text-foreground">
      <div className="app-grid" aria-hidden="true" />
      <div className="app-glow" aria-hidden="true" />

      <header className="relative z-10 border-b border-border/70">
        <nav
          className="mx-auto flex min-h-20 w-full max-w-7xl items-center justify-between gap-4 px-5 sm:px-8 lg:px-12"
          aria-label="主导航"
        >
          <Link
            href="/"
            className="flex items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <span className="grid size-9 place-items-center rounded-xl border border-accent/30 bg-accent/10 text-sm font-bold text-accent">
              T
            </span>
            <span className="text-lg font-semibold tracking-tight">THar</span>
          </Link>

          <div className="flex items-center gap-3">
            {authState === "loading" ? (
              <span className="text-sm text-muted">正在检查登录状态…</span>
            ) : null}

            {authState === "unavailable" ? (
              <span className="hidden text-sm text-danger sm:inline">
                API 暂不可用
              </span>
            ) : null}

            {authState === "authenticated" && user ? (
              <>
                <span className="hidden text-sm text-muted sm:inline">
                  {user.username}
                </span>
                <button
                  type="button"
                  onClick={handleLogout}
                  disabled={isLoggingOut}
                  className="flex min-h-11 cursor-pointer items-center rounded-xl border border-border px-4 text-sm font-medium transition hover:border-muted hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isLoggingOut ? "退出中…" : "退出登录"}
                </button>
              </>
            ) : null}

            {authState === "guest" || authState === "unavailable" ? (
              <Link
                href="/login"
                className="flex min-h-11 items-center rounded-xl bg-accent px-5 text-sm font-semibold text-accent-foreground transition hover:bg-accent-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                登录
              </Link>
            ) : null}
          </div>
        </nav>
      </header>

      <section className="relative z-10 mx-auto flex w-full max-w-7xl flex-col px-5 pb-20 pt-20 sm:px-8 sm:pt-28 lg:px-12 lg:pb-28 lg:pt-36">
        <div className="max-w-4xl">
          <p className="mb-6 font-mono text-xs font-semibold uppercase tracking-[0.22em] text-accent sm:text-sm">
            Intent-first agent runtime
          </p>
          <h1 className="max-w-4xl text-5xl font-semibold leading-[1.02] tracking-[-0.055em] sm:text-6xl lg:text-8xl">
            先理解意图，
            <br />
            再让 Agent 行动。
          </h1>
          <p className="mt-8 max-w-2xl text-base leading-8 text-muted sm:text-lg">
            THar 是面向服务端的 LLM 对话编排器。每个请求都会先经过可信分类与安全策略，
            再进入获得最小权限的 Agent。
          </p>

          <div className="mt-10 flex flex-col items-start gap-4 sm:flex-row sm:items-center">
            {authState === "authenticated" && user ? (
              <Link
                href="/chat"
                className="flex min-h-12 items-center gap-3 rounded-xl bg-accent px-6 text-sm font-semibold text-accent-foreground transition hover:bg-accent-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <span
                  className="size-2 rounded-full bg-accent-foreground"
                  aria-hidden="true"
                />
                进入对话 · {user.username}
              </Link>
            ) : (
              <Link
                href="/login"
                className="flex min-h-12 items-center justify-center rounded-xl bg-accent px-6 text-sm font-semibold text-accent-foreground transition hover:bg-accent-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                登录并开始
              </Link>
            )}
            <span className="text-sm text-muted">
              Cookie 鉴权 · Conversation 隔离 · SSE 输出
            </span>
          </div>
        </div>
      </section>

      <section className="relative z-10 border-t border-border/70 bg-surface/45">
        <div className="mx-auto grid w-full max-w-7xl gap-px bg-border/70 sm:grid-cols-3">
          {principles.map((principle) => (
            <article
              key={principle.number}
              className="min-h-64 bg-background/95 p-8 sm:p-9 lg:p-10"
            >
              <span className="font-mono text-xs font-semibold text-accent">
                {principle.number}
              </span>
              <h2 className="mt-12 text-xl font-semibold tracking-tight">
                {principle.title}
              </h2>
              <p className="mt-4 text-sm leading-7 text-muted">
                {principle.description}
              </p>
            </article>
          ))}
        </div>
      </section>

      <footer className="relative z-10 border-t border-border/70">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-2 px-5 py-8 text-xs text-muted sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-12">
          <span>THar · Trusted intent routing</span>
          <span>Next.js + FastAPI</span>
        </div>
      </footer>
    </main>
  );
}
