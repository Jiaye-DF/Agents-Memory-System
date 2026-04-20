"use client";

import React, {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Slider } from "@/components/ui/Slider";
import { PresetButton } from "@/components/ui/PresetButton";
import { MultiSelect } from "@/components/ui/MultiSelect";
import type { MultiSelectOption } from "@/components/ui/MultiSelect";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { useDialog } from "@/hooks/useDialog";
import { useAgentDraft } from "@/hooks/useAgentDraft";
import {
  useCreateAgentMutation,
  useUpdateAgentMutation,
  useGetAgentQuery,
  useListAgentsQuery,
} from "@/store/agentsApi";
import { useListModelsQuery } from "@/store/modelsApi";
import { useListSkillsQuery } from "@/store/skillsApi";
import { useListAgentLanguagesQuery } from "@/store/agentLanguagesApi";
import { useGetPublicSettingsQuery } from "@/store/systemSettingsApi";
import { useListAgentTemplatesQuery } from "@/store/agentTemplatesApi";
import { composeSystemPrompt } from "@/utils/agentPrompt";
import type { Agent, AgentTemplate } from "@/types";

type Mode = "create" | "edit";

interface AgentFormProps {
  mode: Mode;
  agent?: Agent;
}

interface FormState {
  name: string;
  description: string;
  language: string;
  style: string;
  identity: string;
  role_prompt: string;
  model: string;
  temperature: number;
  max_tokens: number;
  greeting: string;
  response_format: string;
  response_format_example: string;
  visibility: "public" | "private";
  skill_uids: string[];
}

interface FormErrors {
  name?: string;
  temperature?: string;
  max_tokens?: string;
  skill_uids?: string;
}

const DEFAULT_FORM: FormState = {
  name: "",
  description: "",
  language: "",
  style: "",
  identity: "",
  role_prompt: "",
  model: "",
  temperature: 0.7,
  max_tokens: 4096,
  greeting: "",
  response_format: "markdown",
  response_format_example: "",
  visibility: "private",
  skill_uids: [],
};

const TEMPERATURE_PRESETS = [
  { label: "精確", value: 0.2 },
  { label: "自然", value: 0.7 },
  { label: "創意", value: 1.2 },
];

const DEFAULT_JSON_EXAMPLE = `{
  "title": "...",
  "items": [
    { "name": "...", "value": 0 }
  ]
}`;

const TOKEN_PRESETS = [
  { label: "1K", value: 1024 },
  { label: "4K", value: 4096 },
  { label: "8K", value: 8192 },
  { label: "32K", value: 32768 },
];

const DEFAULT_MAX_SKILLS = 10;

interface SectionProps {
  title: string;
  description?: string;
  children: React.ReactNode;
}

const Section = React.memo(function Section({
  title,
  description,
  children,
}: SectionProps): React.ReactNode {
  return (
    <section className="flex flex-col gap-4 rounded-xl border border-border bg-card-bg p-5 shadow-sm">
      <div>
        <h2 className="text-xl font-semibold text-foreground">{title}</h2>
        {description && (
          <p className="mt-1 text-sm text-muted">{description}</p>
        )}
      </div>
      <div className="flex flex-col gap-4">{children}</div>
    </section>
  );
});

interface CopyAgentModalProps {
  agents: Agent[];
  onSelect: (agent: Agent) => void;
  onClose: () => void;
}

const CopyAgentModal = React.memo(function CopyAgentModal({
  agents,
  onSelect,
  onClose,
}: CopyAgentModalProps): React.ReactNode {
  const [search, setSearch] = useState<string>("");

  const handleSearchChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setSearch(e.target.value);
    },
    []
  );

  const filtered = useMemo((): Agent[] => {
    const term = search.trim().toLowerCase();
    if (!term) return agents;
    return agents.filter((a) => {
      return (
        a.name.toLowerCase().includes(term) ||
        (a.description ?? "").toLowerCase().includes(term) ||
        (a.owner_username ?? "").toLowerCase().includes(term)
      );
    });
  }, [agents, search]);

  return (
    <ModalDialog title="從既有 Agent 複製" onClose={onClose} size="md">
      <div className="flex max-h-[70vh] flex-col">
        <input
          type="text"
          value={search}
          onChange={handleSearchChange}
          placeholder="搜尋 Agent 名稱 / 描述 / 作者"
          className="mb-3 min-h-11 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
        />
        <div className="flex-1 overflow-y-auto rounded-xl border border-border">
          {filtered.length === 0 ? (
            <div className="py-8 text-center text-muted">沒有可複製的 Agent</div>
          ) : (
            <ul className="flex flex-col divide-y divide-border">
              {filtered.map((a) => (
                <li key={a.agent_uid}>
                  <button
                    type="button"
                    onClick={() => onSelect(a)}
                    className="flex w-full flex-col items-start gap-1 px-4 py-3 text-left transition-colors hover:cursor-pointer hover:bg-muted-bg"
                  >
                    <div className="flex w-full items-center gap-2">
                      <span className="truncate font-medium text-foreground">
                        {a.name}
                      </span>
                      {a.owner_username && (
                        <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
                          @{a.owner_username}
                        </span>
                      )}
                    </div>
                    {a.description && (
                      <span className="line-clamp-1 text-sm text-muted">
                        {a.description}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="min-h-11 rounded-xl border border-border px-4 py-2 text-base font-medium text-foreground hover:cursor-pointer hover:bg-muted-bg"
          >
            取消
          </button>
        </div>
      </div>
    </ModalDialog>
  );
});

function agentToFormState(
  agent: Agent,
  overrides: Partial<FormState> = {}
): FormState {
  return {
    name: agent.name,
    description: agent.description ?? "",
    language: agent.language ?? "",
    style: agent.style ?? "",
    identity: agent.identity ?? "",
    role_prompt: agent.role_prompt ?? "",
    model: agent.model ?? "",
    temperature:
      typeof agent.temperature === "number" ? agent.temperature : 0.7,
    max_tokens:
      typeof agent.max_tokens === "number" ? agent.max_tokens : 4096,
    greeting: agent.greeting ?? "",
    response_format: agent.response_format ?? "markdown",
    response_format_example: agent.response_format_example ?? "",
    visibility: agent.visibility,
    skill_uids: agent.skill_uids ?? [],
    ...overrides,
  };
}

function applyTemplateValues(
  prev: FormState,
  tpl: AgentTemplate
): FormState {
  const nextFormat = tpl.response_format ?? prev.response_format;
  const nextExample = tpl.response_format_example ?? "";
  return {
    ...prev,
    name: tpl.name ?? prev.name,
    description: tpl.description ?? prev.description,
    language: tpl.language ?? prev.language,
    style: tpl.style ?? prev.style,
    identity: tpl.identity ?? prev.identity,
    role_prompt: tpl.role_prompt ?? prev.role_prompt,
    greeting: tpl.greeting ?? prev.greeting,
    temperature:
      typeof tpl.temperature === "number" ? tpl.temperature : prev.temperature,
    max_tokens:
      typeof tpl.max_tokens === "number" ? tpl.max_tokens : prev.max_tokens,
    response_format: nextFormat,
    response_format_example:
      nextFormat === "json"
        ? nextExample || prev.response_format_example || DEFAULT_JSON_EXAMPLE
        : "",
  };
}

export function AgentForm({
  mode,
  agent,
}: AgentFormProps): React.ReactNode {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { showDialog } = useDialog();

  const [createAgent, { isLoading: creating }] = useCreateAgentMutation();
  const [updateAgent, { isLoading: updating }] = useUpdateAgentMutation();

  const { data: modelsData } = useListModelsQuery();
  const { data: languagesData } = useListAgentLanguagesQuery();
  const { data: skillsData } = useListSkillsQuery({ limit: 50 });
  const { data: publicSettings } = useGetPublicSettingsQuery();
  const { data: templatesData } = useListAgentTemplatesQuery(undefined, {
    skip: mode !== "create",
  });

  const fromUid = mode === "create" ? searchParams?.get("from") ?? null : null;
  const { data: fromAgent } = useGetAgentQuery(fromUid ?? "", {
    skip: !fromUid,
  });

  const { data: listAgentsData } = useListAgentsQuery(
    { limit: 50 },
    { skip: mode !== "create" }
  );

  const { loadDraft, saveDraft, clearDraft } = useAgentDraft<FormState>();

  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [errors, setErrors] = useState<FormErrors>({});
  const [initialized, setInitialized] = useState<boolean>(false);
  const [draftRestored, setDraftRestored] = useState<boolean>(false);
  const [showCopyModal, setShowCopyModal] = useState<boolean>(false);
  const [showTemplatesMenu, setShowTemplatesMenu] = useState<boolean>(false);

  const languages = useMemo(
    () => languagesData?.items ?? [],
    [languagesData]
  );
  const models = useMemo(() => modelsData?.items ?? [], [modelsData]);
  const skills = useMemo(() => skillsData?.items ?? [], [skillsData]);
  const templates = useMemo(
    (): AgentTemplate[] => templatesData?.items ?? [],
    [templatesData]
  );

  const maxSkills = useMemo((): number => {
    const raw = publicSettings?.["agent.max_skills"];
    if (typeof raw === "number" && raw > 0) return raw;
    return DEFAULT_MAX_SKILLS;
  }, [publicSettings]);

  const languageNameMap = useMemo((): Map<string, string> => {
    const map = new Map<string, string>();
    for (const l of languages) {
      map.set(l.code, l.name);
    }
    return map;
  }, [languages]);

  const selectedModel = useMemo(() => {
    return models.find((m) => m.model_id === form.model);
  }, [models, form.model]);

  // 初始化（編輯模式 / 新增模式）— 依外部資料（agent/languages/models/draft）一次性填入 form，
  // 這是合法的同步化需求，不適用 derived-state 改寫。
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (initialized) return;

    if (mode === "edit" && agent) {
      setForm(agentToFormState(agent));
      setInitialized(true);
      return;
    }

    if (mode === "create") {
      // 需等到 languages 與 models 載入後才能決定預設值
      if (!languagesData || !modelsData) return;

      // from=xxx 複製來源
      if (fromUid) {
        if (!fromAgent) return;
        setForm(
          agentToFormState(fromAgent, {
            name: `${fromAgent.name}（副本）`,
            visibility: "private",
          })
        );
        setInitialized(true);
        return;
      }

      // 草稿恢復
      const draft = loadDraft();
      if (draft) {
        setForm(draft);
        setDraftRestored(true);
        setInitialized(true);
        return;
      }

      // 預設值：語言 = is_default 的語言，模型 = is_default 模型
      const defaultLanguage = languages.find((l) => l.is_default);
      const defaultModel = models.find((m) => m.is_default);
      setForm({
        ...DEFAULT_FORM,
        language: defaultLanguage?.code ?? "",
        model: defaultModel?.model_id ?? "",
      });
      setInitialized(true);
    }
  }, [
    mode,
    agent,
    initialized,
    languagesData,
    modelsData,
    languages,
    models,
    fromUid,
    fromAgent,
    loadDraft,
  ]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // 草稿自動儲存（僅 create）
  useEffect(() => {
    if (mode !== "create") return;
    if (!initialized) return;
    saveDraft(form);
  }, [mode, initialized, form, saveDraft]);

  const setField = useCallback(
    <K extends keyof FormState>(field: K, value: FormState[K]): void => {
      setForm((prev) => ({ ...prev, [field]: value }));
    },
    []
  );

  const handleTextChange = useCallback(
    (field: keyof FormState) =>
      (
        e: React.ChangeEvent<
          HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
        >
      ): void => {
        const value = e.target.value;
        setForm((prev) => ({ ...prev, [field]: value }));
        if (field === "name") {
          setErrors((prev) => ({ ...prev, name: undefined }));
        }
      },
    []
  );

  const handleTemperatureChange = useCallback(
    (value: number): void => {
      setField("temperature", value);
      setErrors((prev) => ({ ...prev, temperature: undefined }));
    },
    [setField]
  );

  const handleTemperaturePreset = useCallback(
    (value: number): void => {
      handleTemperatureChange(value);
    },
    [handleTemperatureChange]
  );

  const handleMaxTokensChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      const raw = e.target.value;
      const num = parseInt(raw, 10);
      setForm((prev) => ({
        ...prev,
        max_tokens: Number.isNaN(num) ? 0 : num,
      }));
      setErrors((prev) => ({ ...prev, max_tokens: undefined }));
    },
    []
  );

  const handleMaxTokensPreset = useCallback(
    (value: number): void => {
      setField("max_tokens", value);
      setErrors((prev) => ({ ...prev, max_tokens: undefined }));
    },
    [setField]
  );

  const handleSkillsChange = useCallback(
    (next: string[]): void => {
      setField("skill_uids", next);
      setErrors((prev) => ({ ...prev, skill_uids: undefined }));
    },
    [setField]
  );

  const handleVisibilityChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>): void => {
      const next = e.target.value as "public" | "private";
      setField("visibility", next);
    },
    [setField]
  );

  const handleLanguageChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>): void => {
      setField("language", e.target.value);
    },
    [setField]
  );

  const handleModelChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>): void => {
      setField("model", e.target.value);
    },
    [setField]
  );

  const handleResponseFormatChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>): void => {
      const next = e.target.value;
      setForm((prev) => ({
        ...prev,
        response_format: next,
        response_format_example:
          next === "json" && !prev.response_format_example
            ? DEFAULT_JSON_EXAMPLE
            : prev.response_format_example,
      }));
    },
    []
  );

  const handleResponseFormatExampleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>): void => {
      setField("response_format_example", e.target.value);
    },
    [setField]
  );

  const applyTemplate = useCallback(
    (template: AgentTemplate | null): void => {
      setShowTemplatesMenu(false);
      if (!template) {
        setForm((prev) => ({
          ...DEFAULT_FORM,
          language: prev.language,
          model: prev.model,
        }));
        return;
      }
      setForm((prev) => applyTemplateValues(prev, template));
    },
    []
  );

  const handleOpenCopy = useCallback((): void => {
    setShowCopyModal(true);
  }, []);

  const handleCloseCopy = useCallback((): void => {
    setShowCopyModal(false);
  }, []);

  const handleSelectCopyAgent = useCallback((source: Agent): void => {
    setForm(
      agentToFormState(source, {
        name: `${source.name}（副本）`,
        visibility: "private",
      })
    );
    setShowCopyModal(false);
  }, []);

  const handleClearDraft = useCallback((): void => {
    clearDraft();
    setDraftRestored(false);
    const defaultLanguage = languages.find((l) => l.is_default);
    const defaultModel = models.find((m) => m.is_default);
    setForm({
      ...DEFAULT_FORM,
      language: defaultLanguage?.code ?? "",
      model: defaultModel?.model_id ?? "",
    });
    setErrors({});
  }, [clearDraft, languages, models]);

  const validate = useCallback((): boolean => {
    const newErrors: FormErrors = {};
    if (!form.name.trim()) {
      newErrors.name = "名稱為必填欄位";
    } else if (form.name.length > 100) {
      newErrors.name = "名稱長度不可超過 100 字元";
    }
    if (
      typeof form.temperature !== "number" ||
      Number.isNaN(form.temperature) ||
      form.temperature < 0 ||
      form.temperature > 2
    ) {
      newErrors.temperature = "溫度需介於 0 至 2 之間";
    }
    if (
      typeof form.max_tokens !== "number" ||
      Number.isNaN(form.max_tokens) ||
      form.max_tokens < 1 ||
      form.max_tokens > 200000
    ) {
      newErrors.max_tokens = "Token 數需介於 1 至 200000 之間";
    }
    if (form.skill_uids.length > maxSkills) {
      newErrors.skill_uids = `Skills 數量不可超過 ${maxSkills} 個`;
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [form, maxSkills]);

  const handleCancel = useCallback((): void => {
    if (mode === "create") {
      clearDraft();
      router.push("/agents");
    } else if (agent) {
      router.push(`/agents/${agent.agent_uid}`);
    } else {
      router.push("/agents");
    }
  }, [mode, agent, router, clearDraft]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
      e.preventDefault();
      if (!validate()) return;

      const payload = {
        name: form.name.trim(),
        description: form.description || null,
        language: form.language || null,
        style: form.style || null,
        identity: form.identity || null,
        role_prompt: form.role_prompt || null,
        model: form.model || null,
        temperature:
          typeof form.temperature === "number" ? form.temperature : null,
        max_tokens:
          typeof form.max_tokens === "number" ? form.max_tokens : null,
        greeting: form.greeting || null,
        response_format: form.response_format || "markdown",
        response_format_example:
          form.response_format === "json"
            ? form.response_format_example || null
            : null,
        skill_uids: form.skill_uids,
      };

      try {
        if (mode === "create") {
          await createAgent({
            ...payload,
            visibility: form.visibility,
          }).unwrap();
          clearDraft();
          showDialog({
            type: "info",
            title: "建立成功",
            message: "Agent 已成功建立。",
            onConfirm: () => {
              router.push("/agents");
            },
          });
        } else if (agent) {
          await updateAgent({
            agentUid: agent.agent_uid,
            body: payload,
          }).unwrap();
          showDialog({
            type: "info",
            title: "更新成功",
            message: "Agent 設定已成功更新。",
          });
        }
      } catch (err: unknown) {
        const message =
          typeof err === "string"
            ? err
            : mode === "create"
              ? "建立失敗，請稍後再試"
              : "更新失敗，請稍後再試";
        showDialog({
          type: "error",
          title: "操作失敗",
          message,
        });
      }
    },
    [
      mode,
      form,
      agent,
      validate,
      createAgent,
      updateAgent,
      clearDraft,
      showDialog,
      router,
    ]
  );

  const skillOptions = useMemo((): MultiSelectOption[] => {
    return skills.map((s) => ({
      value: s.skill_uid,
      label: s.owner_username ? `${s.name}（@${s.owner_username}）` : s.name,
      description: s.description,
    }));
  }, [skills]);

  const copyableAgents = useMemo((): Agent[] => {
    return listAgentsData?.items ?? [];
  }, [listAgentsData]);

  const languageName = languageNameMap.get(form.language) ?? form.language;

  const composedPrompt = useMemo((): string => {
    return composeSystemPrompt({
      identity: form.identity,
      languageName,
      style: form.style,
      role_prompt: form.role_prompt,
    });
  }, [form.identity, languageName, form.style, form.role_prompt]);

  const exceedsModelLimit = useMemo((): boolean => {
    if (!selectedModel) return false;
    if (selectedModel.max_output_tokens == null) return false;
    return form.max_tokens > selectedModel.max_output_tokens;
  }, [selectedModel, form.max_tokens]);

  const submitting = creating || updating;

  const toggleTemplatesMenu = useCallback((): void => {
    setShowTemplatesMenu((prev) => !prev);
  }, []);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-bold text-foreground">
          {mode === "create" ? "新增 Agent" : "編輯 Agent"}
        </h1>
        {mode === "create" && (
          <div className="flex items-center gap-2">
            <div className="relative">
              <Button
                variant="secondary"
                size="sm"
                onClick={toggleTemplatesMenu}
              >
                套用範本 ▾
              </Button>
              {showTemplatesMenu && (
                <div className="absolute right-0 top-full z-20 mt-1 w-64 rounded-xl border border-border bg-card-bg p-1 shadow-lg">
                  <button
                    type="button"
                    onClick={() => applyTemplate(null)}
                    className="flex w-full flex-col items-start gap-0.5 rounded-xl px-3 py-2 text-left hover:cursor-pointer hover:bg-muted-bg"
                  >
                    <span className="font-medium text-foreground">空白</span>
                    <span className="text-sm text-muted">清空所有欄位</span>
                  </button>
                  {templates.length === 0 ? (
                    <div className="px-3 py-2 text-sm text-muted">
                      尚無可用範本
                    </div>
                  ) : (
                    templates.map((t) => (
                      <button
                        key={t.agent_template_uid}
                        type="button"
                        onClick={() => applyTemplate(t)}
                        className="flex w-full flex-col items-start gap-0.5 rounded-xl px-3 py-2 text-left hover:cursor-pointer hover:bg-muted-bg"
                      >
                        <span className="font-medium text-foreground">
                          {t.label}
                        </span>
                        {t.description && (
                          <span className="line-clamp-1 text-sm text-muted">
                            {t.description}
                          </span>
                        )}
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
            <Button variant="secondary" size="sm" onClick={handleOpenCopy}>
              從既有 Agent 複製
            </Button>
          </div>
        )}
      </div>

      {mode === "create" && draftRestored && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-info/40 bg-info-bg px-4 py-3 text-info">
          <span className="text-base">已恢復上次未完成的草稿</span>
          <Button
            size="sm"
            variant="secondary"
            onClick={handleClearDraft}
          >
            清除草稿
          </Button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <div className="flex flex-col gap-4">
            <Section title="基本資訊">
              <Input
                label="名稱"
                required
                value={form.name}
                onChange={handleTextChange("name")}
                error={errors.name}
                placeholder="輸入 Agent 名稱"
              />
              <div>
                <label
                  htmlFor="description"
                  className="mb-1.5 block text-base font-medium text-foreground"
                >
                  描述
                </label>
                <textarea
                  id="description"
                  value={form.description}
                  onChange={handleTextChange("description")}
                  placeholder="輸入 Agent 描述"
                  rows={3}
                  className="min-h-11 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
                />
              </div>
              {mode === "create" && (
                <div>
                  <label
                    htmlFor="visibility"
                    className="mb-1.5 block text-base font-medium text-foreground"
                  >
                    可見性
                  </label>
                  <select
                    id="visibility"
                    value={form.visibility}
                    onChange={handleVisibilityChange}
                    className="min-h-11 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground hover:cursor-pointer focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
                  >
                    <option value="private">私人</option>
                    <option value="public">公開</option>
                  </select>
                </div>
              )}
            </Section>

            <Section title="角色設定">
              <Input
                label="身分"
                value={form.identity}
                onChange={handleTextChange("identity")}
                placeholder="例如：資深 Python 工程師"
              />
              <div>
                <label
                  htmlFor="language"
                  className="mb-1.5 block text-base font-medium text-foreground"
                >
                  語言偏好
                </label>
                <select
                  id="language"
                  value={form.language}
                  onChange={handleLanguageChange}
                  className="min-h-11 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground hover:cursor-pointer focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
                >
                  <option value="">未指定</option>
                  {languages.map((l) => (
                    <option key={l.agent_language_uid} value={l.code}>
                      {l.name}（{l.code}）
                      {l.is_default ? "｜預設" : ""}
                    </option>
                  ))}
                </select>
              </div>
              <Input
                label="風格"
                value={form.style}
                onChange={handleTextChange("style")}
                placeholder="例如：專業、友善"
              />
              <div>
                <label
                  htmlFor="role_prompt"
                  className="mb-1.5 block text-base font-medium text-foreground"
                >
                  角色設定
                </label>
                <textarea
                  id="role_prompt"
                  value={form.role_prompt}
                  onChange={handleTextChange("role_prompt")}
                  placeholder="輸入角色設定提示詞"
                  rows={6}
                  className="min-h-11 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
                />
              </div>
            </Section>

            <Section title="模型參數">
              <div>
                <label
                  htmlFor="model"
                  className="mb-1.5 block text-base font-medium text-foreground"
                >
                  模型
                </label>
                <select
                  id="model"
                  value={form.model}
                  onChange={handleModelChange}
                  className="min-h-11 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground hover:cursor-pointer focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
                >
                  <option value="">未指定（使用系統預設）</option>
                  {models.map((m) => (
                    <option key={m.llm_model_uid} value={m.model_id}>
                      {m.display_name}（{m.provider}）
                      {m.is_default ? "｜預設" : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <label
                    htmlFor="temperature"
                    className="text-base font-medium text-foreground"
                  >
                    回答風格
                    <span className="ml-1 text-sm font-normal text-muted">
                      (Temperature)
                    </span>
                  </label>
                  <span className="rounded-xl bg-muted-bg px-2 py-0.5 font-mono text-base text-foreground">
                    {form.temperature.toFixed(1)}
                  </span>
                </div>
                <Slider
                  id="temperature"
                  ariaLabel="回答風格"
                  min={0}
                  max={2}
                  step={0.1}
                  value={form.temperature}
                  onChange={handleTemperatureChange}
                  marks={[
                    { value: 0, label: "0.0" },
                    { value: 1, label: "1.0" },
                    { value: 2, label: "2.0" },
                  ]}
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  {TEMPERATURE_PRESETS.map((p) => (
                    <PresetButton
                      key={p.label}
                      active={Math.abs(form.temperature - p.value) < 0.0001}
                      onClick={() => handleTemperaturePreset(p.value)}
                    >
                      {p.label} {p.value.toFixed(1)}
                    </PresetButton>
                  ))}
                </div>
                {errors.temperature && (
                  <p className="mt-1 text-base text-destructive">
                    {errors.temperature}
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="max_tokens"
                  className="mb-1.5 block text-base font-medium text-foreground"
                >
                  最大 Token 數
                </label>
                <div className="mb-2 flex flex-wrap gap-2">
                  {TOKEN_PRESETS.map((p) => (
                    <PresetButton
                      key={p.label}
                      active={form.max_tokens === p.value}
                      onClick={() => handleMaxTokensPreset(p.value)}
                    >
                      {p.label}
                    </PresetButton>
                  ))}
                </div>
                <input
                  id="max_tokens"
                  type="number"
                  min={1}
                  max={200000}
                  value={Number.isNaN(form.max_tokens) ? "" : form.max_tokens}
                  onChange={handleMaxTokensChange}
                  className={`min-h-11 w-full rounded-xl border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20 ${
                    errors.max_tokens
                      ? "border-destructive"
                      : "border-input-border"
                  }`}
                />
                {errors.max_tokens && (
                  <p className="mt-1 text-base text-destructive">
                    {errors.max_tokens}
                  </p>
                )}
                {exceedsModelLimit && selectedModel && (
                  <p className="mt-1 text-base text-destructive">
                    超過 {selectedModel.display_name} 建議上限{" "}
                    {selectedModel.max_output_tokens} tokens，實際請求可能被截斷。
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="response_format"
                  className="mb-1.5 block text-base font-medium text-foreground"
                >
                  回覆格式
                </label>
                <select
                  id="response_format"
                  value={form.response_format}
                  onChange={handleResponseFormatChange}
                  className="min-h-11 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground hover:cursor-pointer focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
                >
                  <option value="markdown">Markdown</option>
                  <option value="plain_text">純文字</option>
                  <option value="json">JSON</option>
                </select>

                {form.response_format === "json" && (
                  <div className="mt-3">
                    <label
                      htmlFor="response_format_example"
                      className="mb-1.5 block text-base font-medium text-foreground"
                    >
                      JSON 範例
                    </label>
                    <p className="mb-2 text-sm text-muted">
                      提供期望的回覆結構範例，LLM 會依此格式輸出。
                    </p>
                    <textarea
                      id="response_format_example"
                      value={form.response_format_example}
                      onChange={handleResponseFormatExampleChange}
                      placeholder={DEFAULT_JSON_EXAMPLE}
                      rows={8}
                      spellCheck={false}
                      className="w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 font-mono text-sm text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
                    />
                  </div>
                )}
              </div>
            </Section>

            <Section title="互動">
              <div>
                <label
                  htmlFor="greeting"
                  className="mb-1.5 block text-base font-medium text-foreground"
                >
                  開場白
                </label>
                <textarea
                  id="greeting"
                  value={form.greeting}
                  onChange={handleTextChange("greeting")}
                  placeholder="Agent 對話開始時的第一句話"
                  rows={3}
                  className="min-h-11 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
                />
              </div>

              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <label className="text-base font-medium text-foreground">
                    Skills
                  </label>
                  <span className="text-sm text-muted">
                    已選 {form.skill_uids.length} / {maxSkills}
                  </span>
                </div>
                <MultiSelect
                  options={skillOptions}
                  value={form.skill_uids}
                  onChange={handleSkillsChange}
                  maxSelected={maxSkills}
                  placeholder="搜尋並選擇 Skills..."
                  emptyMessage="沒有可用的 Skills"
                  limitReachedMessage={`已達上限 ${maxSkills} 個 Skills`}
                />
                {errors.skill_uids && (
                  <p className="mt-1 text-base text-destructive">
                    {errors.skill_uids}
                  </p>
                )}
              </div>
            </Section>
          </div>

          <div className="xl:sticky xl:top-4 xl:self-start">
            <section className="flex flex-col gap-3 rounded-xl border border-border bg-card-bg p-5 shadow-sm">
              <div>
                <h2 className="text-xl font-semibold text-foreground">
                  實際送出的 System Prompt
                </h2>
                <p className="mt-1 text-sm text-muted">
                  依 身分 → 語言 → 風格 → 角色設定 順序組裝，即時更新。
                </p>
              </div>
              {composedPrompt ? (
                <pre className="max-h-120 overflow-auto whitespace-pre-wrap rounded-xl bg-muted-bg p-4 font-mono text-sm text-foreground">
                  {composedPrompt}
                </pre>
              ) : (
                <div className="rounded-xl border border-dashed border-input-border bg-muted-bg/60 p-4 text-center text-sm text-muted">
                  填寫身分 / 語言 / 風格 / 角色設定後，此區會即時預覽。
                </div>
              )}
            </section>
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          <Button type="submit" loading={submitting}>
            {mode === "create" ? "建立 Agent" : "儲存變更"}
          </Button>
          <Button type="button" variant="secondary" onClick={handleCancel}>
            取消
          </Button>
        </div>
      </form>

      {showCopyModal && (
        <CopyAgentModal
          agents={copyableAgents}
          onSelect={handleSelectCopyAgent}
          onClose={handleCloseCopy}
        />
      )}
    </div>
  );
}
