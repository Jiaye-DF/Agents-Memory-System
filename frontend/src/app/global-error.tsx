"use client";

interface GlobalErrorProps {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}

export default function GlobalError({
  error,
  unstable_retry,
}: GlobalErrorProps): React.ReactNode {
  return (
    <html lang="zh-Hant">
      <body
        style={{
          margin: 0,
          display: "flex",
          minHeight: "100vh",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "Arial, Helvetica, sans-serif",
        }}
      >
        <div style={{ textAlign: "center", padding: "2rem" }}>
          <h2 style={{ fontSize: "1.5rem", marginBottom: "1rem" }}>
            系統發生嚴重錯誤
          </h2>
          <p style={{ color: "#6b7280", marginBottom: "1.5rem" }}>
            {error.digest
              ? `錯誤代碼：${error.digest}`
              : "無法載入頁面，請稍後再試"}
          </p>
          <button
            onClick={unstable_retry}
            style={{
              padding: "0.75rem 1.5rem",
              borderRadius: "0.75rem",
              border: "none",
              backgroundColor: "#2563eb",
              color: "white",
              fontSize: "0.875rem",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            重試
          </button>
        </div>
      </body>
    </html>
  );
}
