"use client";

import React, { useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useDispatch } from "react-redux";
import { Button } from "@/components/ui/Button";
import { PageLoading } from "@/components/ui/Loading";
import { useDialog } from "@/hooks/useDialog";
import { useGetAgentQuery } from "@/store/agentsApi";
import { useListAgentLanguagesQuery } from "@/store/agentLanguagesApi";
import { baseApi } from "@/store/api";
import type { AppDispatch } from "@/store/store";
import {
  downloadText,
  triggerBrowserDownload,
} from "@/lib/api/download";
import { useAuth } from "@/hooks/useAuth";
import { formatDateTime } from "@/utils/datetime";

export default function AgentDetailPage(): React.ReactNode {
  const params = useParams<{ uid: string }>();
  const agentUid = params.uid;
  const { userUid } = useAuth();
  const { showDialog } = useDialog();
  const dispatch = useDispatch<AppDispatch>();

  const { data: agent, isLoading } = useGetAgentQuery(agentUid);
  const { data: languagesData } = useListAgentLanguagesQuery();

  const handleDownload = useCallback(async (): Promise<void> => {
    try {
      const result = await downloadText(`/agents/${agentUid}/download`);
      if (!result.ok || result.text === undefined) {
        showDialog({
          type: "error",
          title: "下載失敗",
          message: "無法下載 AGENTS.md 檔案",
        });
        return;
      }
      const blob = new Blob([result.text], { type: "text/markdown" });
      triggerBrowserDownload(blob, "AGENTS.md");
      // 下載連動 Agent + 關聯 Skills 計數，需讓相關列表 / 排行 / 收藏 refetch
      dispatch(
        baseApi.util.invalidateTags([
          "Agents",
          "Skills",
          "Rankings",
          "Favorites",
        ]),
      );
    } catch {
      showDialog({
        type: "error",
        title: "下載失敗",
        message: "下載過程中發生錯誤",
      });
    }
  }, [agentUid, showDialog, dispatch]);

  if (isLoading) {
    return <PageLoading />;
  }

  if (!agent) {
    return (
      <div className="py-12 text-center text-muted">找不到指定的 Agent</div>
    );
  }

  const isOwner = agent.owner_uid === userUid;
  const languageLabel = (() => {
    if (!agent.language) return null;
    const match = languagesData?.items.find((l) => l.code === agent.language);
    return match?.name ?? agent.language;
  })();

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-foreground">{agent.name}</h1>
        <div className="flex gap-2">
          {isOwner && (
            <Link href={`/agents/${agentUid}/edit`}>
              <Button variant="secondary">編輯</Button>
            </Link>
          )}
          <Button variant="secondary" onClick={handleDownload}>
            下載 AGENTS.md
          </Button>
        </div>
      </div>

      <div className="rounded-xl bg-card-bg p-6 shadow-sm">
        <div className="flex flex-col gap-6">
          <div className="flex items-center gap-3">
            <span
              className={`rounded-xl px-3 py-1 text-base font-medium ${
                agent.visibility === "public"
                  ? "bg-info-bg text-info"
                  : "bg-muted-bg text-muted"
              }`}
            >
              {agent.visibility === "public" ? "公開" : "私人"}
            </span>
            <span className="text-base text-muted">
              建立於 {formatDateTime(agent.created_at)}
            </span>
          </div>

          {agent.description && (
            <div>
              <h2 className="mb-2 text-base font-semibold text-muted">描述</h2>
              <p className="whitespace-pre-wrap text-foreground">
                {agent.description}
              </p>
            </div>
          )}

          {agent.identity && (
            <div>
              <h2 className="mb-2 text-base font-semibold text-muted">身分</h2>
              <p className="whitespace-pre-wrap text-foreground">
                {agent.identity}
              </p>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {languageLabel && (
              <div>
                <h2 className="mb-2 text-base font-semibold text-muted">
                  語言偏好
                </h2>
                <p className="text-foreground">{languageLabel}</p>
              </div>
            )}
            {agent.style && (
              <div>
                <h2 className="mb-2 text-base font-semibold text-muted">風格</h2>
                <p className="text-foreground">{agent.style}</p>
              </div>
            )}
          </div>

          {agent.role_prompt && (
            <div>
              <h2 className="mb-2 text-base font-semibold text-muted">
                角色設定
              </h2>
              <div className="whitespace-pre-wrap rounded-xl bg-muted-bg p-4 text-base text-foreground">
                {agent.role_prompt}
              </div>
            </div>
          )}

          <div>
            <h2 className="mb-2 text-base font-semibold text-muted">
              關聯 Skills
            </h2>
            {agent.skills.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {agent.skills.map((s) => (
                  <Link
                    key={s.skill_uid}
                    href={`/skills/${s.skill_uid}`}
                    className="rounded-xl bg-muted-bg px-3 py-1 text-base text-foreground hover:cursor-pointer hover:bg-sidebar-hover"
                  >
                    {s.name}
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-base text-muted italic">尚無關聯 Skills</p>
            )}
          </div>

          <div className="border-t border-border pt-4 text-base text-muted">
            最後更新：{formatDateTime(agent.updated_at)}
          </div>
        </div>
      </div>
    </div>
  );
}
