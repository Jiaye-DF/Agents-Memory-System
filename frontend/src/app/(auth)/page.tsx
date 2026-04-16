import { Logo } from "@/components/layout/Logo";

export default function LoginPage(): React.ReactNode {
  return (
    <div className="w-full max-w-md rounded-xl bg-card-bg p-8 shadow-lg">
      <div className="mb-6 flex flex-col items-center gap-2">
        <Logo className="h-12 w-12" />
        <h1 className="text-2xl font-bold text-foreground">Agents Platform</h1>
        <p className="text-sm text-muted">請登入以繼續</p>
      </div>
      <div className="flex flex-col gap-4">
        <p className="text-center text-sm text-muted">
          登入表單（後續 Phase 實作）
        </p>
      </div>
    </div>
  );
}
