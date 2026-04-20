import { getAccessToken } from "./client";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

interface DownloadResult {
  ok: boolean;
  blob?: Blob;
  text?: string;
  headers?: Headers;
  status: number;
}

async function requestRaw(path: string): Promise<Response> {
  const token = getAccessToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return fetch(`${BASE_URL}${path}`, {
    method: "GET",
    headers,
    credentials: "include",
  });
}

export async function downloadText(path: string): Promise<DownloadResult> {
  const response = await requestRaw(path);
  if (!response.ok) {
    return { ok: false, status: response.status };
  }
  const text = await response.text();
  return { ok: true, text, headers: response.headers, status: response.status };
}

export async function downloadBlob(path: string): Promise<DownloadResult> {
  const response = await requestRaw(path);
  if (!response.ok) {
    return { ok: false, status: response.status };
  }
  const blob = await response.blob();
  return { ok: true, blob, headers: response.headers, status: response.status };
}

export function extractFilename(
  headers: Headers | undefined,
  fallback: string
): string {
  if (!headers) return fallback;
  const contentDisposition = headers.get("content-disposition");
  if (!contentDisposition) return fallback;
  const match = contentDisposition.match(
    /filename\*?=(?:UTF-8'')?["']?([^"';\n]+)/i
  );
  if (match && match[1]) {
    try {
      return decodeURIComponent(match[1]);
    } catch {
      return match[1];
    }
  }
  return fallback;
}

export function triggerBrowserDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
