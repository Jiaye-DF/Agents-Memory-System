/**
 * DF-SSO back-channel logout 接收端（契約 #4）。
 *
 * 中央 SSO 在使用者登出時會 POST 此 endpoint 通知本系統撤銷 session。
 * 此處先驗 HMAC + timestamp（防 replay），再轉發到 backend 觸發實際撤銷。
 *
 * 注意：必須跑 Node runtime（不能用 edge runtime — Next.js middleware / edge 沒有 node:crypto）。
 */
import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

export const runtime = "nodejs";

const SSO_APP_SECRET = process.env.SSO_APP_SECRET ?? "";
const BACKEND_URL = process.env.BACKEND_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "";
const MAX_TIMESTAMP_DRIFT_MS = 30_000;

interface BackChannelPayload {
  user_id?: string;
  timestamp?: number;
  signature?: string;
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (!SSO_APP_SECRET) {
    return NextResponse.json({ error: "sso_not_configured" }, { status: 503 });
  }

  let body: BackChannelPayload;
  try {
    body = (await request.json()) as BackChannelPayload;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const { user_id, timestamp, signature } = body;
  if (!user_id || !timestamp || !signature) {
    return NextResponse.json({ error: "Missing fields" }, { status: 400 });
  }

  if (Math.abs(Date.now() - timestamp) > MAX_TIMESTAMP_DRIFT_MS) {
    return NextResponse.json({ error: "Timestamp expired" }, { status: 401 });
  }

  const expected = crypto
    .createHmac("sha256", SSO_APP_SECRET)
    .update(`${user_id}:${timestamp}`)
    .digest("hex");

  const sigBuf = Buffer.from(signature);
  const expBuf = Buffer.from(expected);
  if (
    sigBuf.length !== expBuf.length ||
    !crypto.timingSafeEqual(sigBuf, expBuf)
  ) {
    return NextResponse.json({ error: "Invalid signature" }, { status: 401 });
  }

  // 轉發到 backend 撤銷該使用者的 local session（backend 也會再驗一次 HMAC，防禦性）
  if (BACKEND_URL) {
    try {
      await fetch(`${BACKEND_URL}/auth/sso/back-channel-logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id, timestamp, signature }),
        cache: "no-store",
        signal: AbortSignal.timeout(8000),
      });
    } catch {
      // backend 不可達也回 success：本端 cookie 已清，使用者下次 /me 時會被擋
    }
  }

  return NextResponse.json({ success: true });
}
