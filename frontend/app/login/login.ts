import { apiRequest } from "@/shared/api/client";

import type { LoginCredentials, LoginResponse } from "./types";

export function login(credentials: LoginCredentials): Promise<LoginResponse> {
  return apiRequest<LoginResponse>("/api/v1/users/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}
