"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { ApiError } from "@/shared/api/client";

import { login } from "../login";

export function LoginForm() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const normalizedUsername = username.trim();
    if (!normalizedUsername || !password) {
      setError("请输入用户名和密码。");
      return;
    }

    setIsSubmitting(true);
    try {
      await login({ username: normalizedUsername, password });
      router.replace("/chat");
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.message
          : "暂时无法连接服务，请确认后端已经启动。",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit} noValidate>
      <div className="space-y-2">
        <label
          className="block text-sm font-medium text-foreground"
          htmlFor="username"
        >
          用户名
        </label>
        <input
          id="username"
          name="username"
          type="text"
          autoComplete="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          disabled={isSubmitting}
          aria-invalid={Boolean(error)}
          className="h-12 w-full rounded-xl border border-border bg-surface px-4 text-base text-foreground outline-none transition placeholder:text-muted focus:border-accent focus:ring-4 focus:ring-accent/10 disabled:cursor-not-allowed disabled:opacity-60"
          placeholder="请输入用户名"
        />
      </div>

      <div className="space-y-2">
        <label
          className="block text-sm font-medium text-foreground"
          htmlFor="password"
        >
          密码
        </label>
        <div className="relative">
          <input
            id="password"
            name="password"
            type={showPassword ? "text" : "password"}
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={isSubmitting}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? "login-error" : undefined}
            className="h-12 w-full rounded-xl border border-border bg-surface px-4 pr-20 text-base text-foreground outline-none transition placeholder:text-muted focus:border-accent focus:ring-4 focus:ring-accent/10 disabled:cursor-not-allowed disabled:opacity-60"
            placeholder="请输入密码"
          />
          <button
            type="button"
            onClick={() => setShowPassword((current) => !current)}
            disabled={isSubmitting}
            className="absolute inset-y-0 right-1 min-w-16 cursor-pointer rounded-lg px-3 text-sm font-medium text-muted transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-60"
            aria-label={showPassword ? "隐藏密码" : "显示密码"}
          >
            {showPassword ? "隐藏" : "显示"}
          </button>
        </div>
      </div>

      {error ? (
        <p
          id="login-error"
          role="alert"
          className="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm leading-6 text-danger"
        >
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={isSubmitting}
        className="flex h-12 w-full cursor-pointer items-center justify-center rounded-xl bg-accent px-5 text-sm font-semibold text-accent-foreground transition hover:bg-accent-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? "正在登录…" : "登录"}
      </button>

      <p className="text-center text-xs leading-5 text-muted">
        演示账号：admin / password 或 tony / 123456
      </p>
    </form>
  );
}
