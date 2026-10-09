import type { Metadata } from "next";
import Link from "next/link";

import { LoginForm } from "./components/LoginForm";

export const metadata: Metadata = {
  title: "登录 · THar",
  description: "登录 THar 意图优先 Agent 编排器",
};

export default function LoginPage() {
  return (
    <main className="grid min-h-dvh bg-background lg:grid-cols-[1.05fr_0.95fr]">
      <section className="relative hidden overflow-hidden border-r border-border lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-16">
        <div className="app-glow" aria-hidden="true" />

        <Link
          href="/"
          className="relative z-10 flex w-fit items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <span className="grid size-9 place-items-center rounded-xl border border-accent/30 bg-accent/10 text-sm font-bold text-accent">
            T
          </span>
          <span className="text-lg font-semibold tracking-tight text-foreground">
            THar
          </span>
        </Link>

        <div className="relative z-10 max-w-xl pb-16">
          <p className="mb-5 font-mono text-xs font-semibold uppercase tracking-[0.22em] text-accent">
            Intent-first orchestration
          </p>
          <h1 className="text-5xl font-semibold leading-[1.08] tracking-[-0.04em] text-foreground xl:text-6xl">
            每一次行动，
            <br />
            都从理解开始。
          </h1>
          <p className="mt-7 max-w-lg text-base leading-8 text-muted">
            THar 会先识别请求意图并执行安全策略，再将任务交给获得最小权限的
            Agent。
          </p>
        </div>

        <p className="relative z-10 text-xs text-muted">
          Trusted intent routing for LLM agents
        </p>
      </section>

      <section className="flex items-center justify-center px-5 py-10 sm:px-8 lg:px-12">
        <div className="w-full max-w-md">
          <Link
            href="/"
            className="mb-12 flex w-fit items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent lg:hidden"
          >
            <span className="grid size-9 place-items-center rounded-xl border border-accent/30 bg-accent/10 text-sm font-bold text-accent">
              T
            </span>
            <span className="text-lg font-semibold text-foreground">THar</span>
          </Link>

          <div className="mb-8">
            <p className="mb-3 text-sm font-medium text-accent">欢迎回来</p>
            <h2 className="text-3xl font-semibold tracking-[-0.03em] text-foreground sm:text-4xl">
              登录你的账号
            </h2>
            <p className="mt-3 text-sm leading-6 text-muted">
              使用账号密码继续进入 THar。
            </p>
          </div>

          <LoginForm />

          <Link
            href="/"
            className="mt-8 flex min-h-11 items-center justify-center text-sm font-medium text-muted transition hover:text-foreground focus-visible:rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            返回主页
          </Link>
        </div>
      </section>
    </main>
  );
}
