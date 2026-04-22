import { getAccessToken } from "./client";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

interface StreamRequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
}

export async function openStream(
  path: string,
  options: StreamRequestOptions = {}
): Promise<Response> {
  const { method = "POST", body } = options;
  const token = getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const init: RequestInit = {
    method,
    headers,
    credentials: "include",
  };
  if (body !== undefined && method !== "GET") {
    init.body = JSON.stringify(body);
  }
  return fetch(`${BASE_URL}${path}`, init);
}
