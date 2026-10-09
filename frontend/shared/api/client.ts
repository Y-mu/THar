type ApiErrorPayload = {
  detail?: string;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    let message = `请求失败（${response.status}）`;

    try {
      const payload = (await response.json()) as ApiErrorPayload;
      if (payload.detail) {
        message = payload.detail;
      }
    } catch {
      // 非 JSON 错误响应保留状态码信息。
    }

    throw new ApiError(message, response.status);
  }

  return response;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await apiFetch(path, init);

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
