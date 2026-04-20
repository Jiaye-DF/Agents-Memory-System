"use client";

import React, { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { useDialog } from "@/hooks/useDialog";
import { useCreateAgentMutation } from "@/store/agentsApi";
import { useListModelsQuery } from "@/store/modelsApi";

interface FormState {
  name: string;
  description: string;
  language: string;
  style: string;
  identity: string;
  role_prompt: string;
  model: string;
  temperature: string;
  max_tokens: string;
  greeting: string;
  response_format: string;
  visibility: "public" | "private";
}

interface FormErrors {
  name?: string;
  temperature?: string;
  max_tokens?: string;
}

const INITIAL_FORM: FormState = {
  name: "",
  description: "",
  language: "",
  style: "",
  identity: "",
  role_prompt: "",
  model: "",
  temperature: "0.7",
  max_tokens: "4096",
  greeting: "",
  response_format: "markdown",
  visibility: "private",
};

export default function AgentNewPage(): React.ReactNode {
  const router = useRouter();
  const { showDialog } = useDialog();
  const [createAgent, { isLoading }] = useCreateAgentMutation();
  const { data: modelsData } = useListModelsQuery();

  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [errors, setErrors] = useState<FormErrors>({});

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
    if (form.temperature) {
      const temp = parseFloat(form.temperature);
      if (isNaN(temp) || temp < 0 || temp > 2) {
        newErrors.temperature = "溫度需介於 0 至 2 之間";
      }
    }
    if (form.max_tokens) {
      const tokens = parseInt(form.max_tokens, 10);
      if (isNaN(tokens) || tokens < 1 || tokens > 200000) {
        newErrors.max_tokens = "Token 數需介於 1 至 200000 之間";
      }
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [form.name, form.temperature, form.max_tokens]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
      e.preventDefault();
      if (!validate()) return;

      try {
        await createAgent({
          name: form.name.trim(),
          description: form.description || null,
          language: form.language || null,
          style: form.style || null,
          identity: form.identity || null,
          role_prompt: form.role_prompt || null,
          model: form.model || null,
          temperature: form.temperature ? parseFloat(form.temperature) : null,
          max_tokens: form.max_tokens ? parseInt(form.max_tokens, 10) : null,
          greeting: form.greeting || null,
          response_format: form.response_format || "markdown",
          visibility: form.visibility,
          skill_uids: [],
        }).unwrap();

        showDialog({
          type: "info",
          title: "建立成功",
          message: "Agent 已成功建立。",
          onConfirm: () => {
            router.push("/agents");
          },
        });
      } catch (err: unknown) {
        const message =
          typeof err === "string" ? err : "建立失敗，請稍後再試";
        showDialog({
          type: "error",
          title: "操作失敗",
          message,
        });
      }
    },
    [form, validate, createAgent, showDialog, router]
  );

  return (
    <div>
      <h1 className="mb-4 text-3xl font-bold text-foreground">新增 Agent</h1>
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
              className="mb-1.5 block text-base font-medium text-foreground"
            >
              描述
            </label>
            <textarea
              id="description"
              value={form.description}
              onChange={handleChange("description")}
              placeholder="輸入 Agent 描述"
              rows={3}
              className="min-h-[44px] w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
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
              className="mb-1.5 block text-base font-medium text-foreground"
            >
              角色設定
            </label>
            <textarea
              id="role_prompt"
              value={form.role_prompt}
              onChange={handleChange("role_prompt")}
              placeholder="輸入角色設定提示詞"
              rows={5}
              className="min-h-[44px] w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="w-full">
              <label
                htmlFor="model"
                className="mb-1.5 block text-base font-medium text-foreground"
              >
                模型
              </label>
              <select
                id="model"
                value={form.model}
                onChange={handleChange("model")}
                className="min-h-[44px] w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground hover:cursor-pointer focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
              >
                <option value="">預設</option>
                {modelsData?.items?.map((m) => (
                  <option key={m.model_id} value={m.model_id}>
                    {m.display_name}（{m.provider}）
                  </option>
                ))}
              </select>
            </div>
            <Input
              label="溫度 (Temperature)"
              value={form.temperature}
              onChange={handleChange("temperature")}
              placeholder="0.0 ~ 2.0"
              error={errors.temperature}
            />
            <Input
              label="最大 Token 數"
              value={form.max_tokens}
              onChange={handleChange("max_tokens")}
              placeholder="例如：4096"
              error={errors.max_tokens}
            />
          </div>

          <div className="w-full">
            <label
              htmlFor="greeting"
              className="mb-1.5 block text-base font-medium text-foreground"
            >
              開場白
            </label>
            <textarea
              id="greeting"
              value={form.greeting}
              onChange={handleChange("greeting")}
              placeholder="Agent 對話開始時的第一句話"
              rows={2}
              className="min-h-[44px] w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
            />
          </div>

          <div className="w-full">
            <label
              htmlFor="response_format"
              className="mb-1.5 block text-base font-medium text-foreground"
            >
              回覆格式
            </label>
            <select
              id="response_format"
              value={form.response_format}
              onChange={handleChange("response_format")}
              className="min-h-[44px] w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground hover:cursor-pointer focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
            >
              <option value="markdown">Markdown</option>
              <option value="plain_text">純文字</option>
              <option value="json">JSON</option>
            </select>
          </div>

          <div className="w-full">
            <label
              htmlFor="visibility"
              className="mb-1.5 block text-base font-medium text-foreground"
            >
              可見性
            </label>
            <select
              id="visibility"
              value={form.visibility}
              onChange={handleChange("visibility")}
              className="min-h-[44px] w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground hover:cursor-pointer focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
            >
              <option value="private">私人</option>
              <option value="public">公開</option>
            </select>
          </div>

          <div className="w-full">
            <label className="mb-1.5 block text-base font-medium text-foreground">
              Skills（尚未開放）
            </label>
            <div className="rounded-xl border border-dashed border-input-border bg-muted-bg p-4 text-center text-base text-muted">
              Skills 選擇器將於 Skills 功能完成後啟用
            </div>
          </div>

          <div className="flex gap-3 pt-2">
            <Button type="submit" loading={isLoading}>
              建立 Agent
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => router.push("/agents")}
            >
              取消
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
