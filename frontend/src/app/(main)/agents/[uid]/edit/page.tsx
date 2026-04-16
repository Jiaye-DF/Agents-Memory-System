"use client";

import React, { useState, useCallback, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { PageLoading } from "@/components/ui/Loading";
import { useDialog } from "@/hooks/useDialog";
import { useGetAgentQuery, useUpdateAgentMutation } from "@/store/agentsApi";

interface FormState {
  name: string;
  description: string;
  language: string;
  style: string;
  identity: string;
  role_prompt: string;
}

interface FormErrors {
  name?: string;
}

export default function AgentEditPage(): React.ReactNode {
  const router = useRouter();
  const params = useParams<{ uid: string }>();
  const agentUid = params.uid;
  const { showDialog } = useDialog();

  const { data: agent, isLoading: isLoadingAgent } =
    useGetAgentQuery(agentUid);
  const [updateAgent, { isLoading: isUpdating }] = useUpdateAgentMutation();

  const [form, setForm] = useState<FormState>({
    name: "",
    description: "",
    language: "",
    style: "",
    identity: "",
    role_prompt: "",
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [initialized, setInitialized] = useState<boolean>(false);

  useEffect(() => {
    if (agent && !initialized) {
      setForm({
        name: agent.name,
        description: agent.description ?? "",
        language: agent.language ?? "",
        style: agent.style ?? "",
        identity: agent.identity ?? "",
        role_prompt: agent.role_prompt ?? "",
      });
      setInitialized(true);
    }
  }, [agent, initialized]);

  const handleChange = useCallback(
    (field: keyof FormState) =>
      (
        e: React.ChangeEvent<
          HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
        >
      ): void => {
        setForm((prev) => ({ ...prev, [field]: e.target.value }));
        if (field === "name") {
          setErrors((prev) => ({ ...prev, name: undefined }));
        }
      },
    []
  );

  const validate = useCallback((): boolean => {
    const newErrors: FormErrors = {};
    if (!form.name.trim()) {
      newErrors.name = "名稱為必填欄位";
    } else if (form.name.length > 100) {
      newErrors.name = "名稱長度不可超過 100 字元";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [form.name]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
      e.preventDefault();
      if (!validate()) return;

      try {
        await updateAgent({
          agentUid,
          body: {
            name: form.name.trim(),
            description: form.description || null,
            language: form.language || null,
            style: form.style || null,
            identity: form.identity || null,
            role_prompt: form.role_prompt || null,
          },
        }).unwrap();

        showDialog({
          type: "info",
          title: "更新成功",
          message: "Agent 設定已成功更新。",
        });
      } catch (err: unknown) {
        const message =
          typeof err === "string" ? err : "更新失敗，請稍後再試";
        showDialog({
          type: "error",
          title: "操作失敗",
          message,
        });
      }
    },
    [form, validate, updateAgent, agentUid, showDialog]
  );

  if (isLoadingAgent) {
    return <PageLoading />;
  }

  if (!agent) {
    return (
      <div className="py-12 text-center text-muted">找不到指定的 Agent</div>
    );
  }

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold text-foreground">編輯 Agent</h1>
      <div className="rounded-xl bg-card-bg p-6 shadow-sm">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input
            label="名稱"
            required
            value={form.name}
            onChange={handleChange("name")}
            error={errors.name}
            placeholder="輸入 Agent 名稱"
          />

          <div className="w-full">
            <label
              htmlFor="description"
              className="mb-1.5 block text-sm font-medium text-foreground"
            >
              描述
            </label>
            <textarea
              id="description"
              value={form.description}
              onChange={handleChange("description")}
              placeholder="輸入 Agent 描述"
              rows={3}
              className="min-h-[44px] w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-sm text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Input
              label="語言偏好"
              value={form.language}
              onChange={handleChange("language")}
              placeholder="例如：繁體中文"
            />
            <Input
              label="風格"
              value={form.style}
              onChange={handleChange("style")}
              placeholder="例如：專業、友善"
            />
          </div>

          <Input
            label="身分"
            value={form.identity}
            onChange={handleChange("identity")}
            placeholder="輸入 Agent 身分設定"
          />

          <div className="w-full">
            <label
              htmlFor="role_prompt"
              className="mb-1.5 block text-sm font-medium text-foreground"
            >
              角色設定
            </label>
            <textarea
              id="role_prompt"
              value={form.role_prompt}
              onChange={handleChange("role_prompt")}
              placeholder="輸入角色設定提示詞"
              rows={5}
              className="min-h-[44px] w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-sm text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
            />
          </div>

          <div className="w-full">
            <label className="mb-1.5 block text-sm font-medium text-foreground">
              Skills（尚未開放）
            </label>
            <div className="rounded-xl border border-dashed border-input-border bg-muted-bg p-4 text-center text-sm text-muted">
              Skills 選擇器將於 Skills 功能完成後啟用
            </div>
          </div>

          <div className="flex gap-3 pt-2">
            <Button type="submit" loading={isUpdating}>
              儲存變更
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => router.push(`/agents/${agentUid}`)}
            >
              取消
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
