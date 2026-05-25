"use client";

import React, { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { useDialog } from "@/hooks/useDialog";
import { useSetEntityTagsMutation } from "@/store/tagsApi";
import type { EntityType, TagSummary } from "@/types";
import { TagInput } from "./TagInput";
import { TagChip } from "./TagChip";

interface TagsCardProps {
  entityType: EntityType;
  entityUid: string;
  initialTags: TagSummary[];
  /** 是否可編輯（非 owner 時設 false）。 */
  canEdit: boolean;
}

const ENTITY_LABEL: Record<EntityType, string> = {
  skill: "Skill",
  script: "Script",
  agent: "Agent",
};

export const TagsCard = React.memo(function TagsCard({
  entityType,
  entityUid,
  initialTags,
  canEdit,
}: TagsCardProps): React.ReactNode {
  const { showDialog } = useDialog();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<TagSummary[]>(initialTags);
  const [setEntityTags, { isLoading }] = useSetEntityTagsMutation();

  // 進入編輯模式時同步最新值；退出後若伺服器資料更新也跟著更新
  useEffect(() => {
    if (!editing) setDraft(initialTags);
  }, [initialTags, editing]);

  const handleStartEdit = useCallback((): void => {
    setDraft(initialTags);
    setEditing(true);
  }, [initialTags]);

  const handleCancel = useCallback((): void => {
    setDraft(initialTags);
    setEditing(false);
  }, [initialTags]);

  const handleSave = useCallback(async (): Promise<void> => {
    // 全部送 names，後端自動 find-or-create
    const names = draft.map((t) => t.name);
    try {
      await setEntityTags({
        entityType,
        entityUid,
        body: { names },
      }).unwrap();
      setEditing(false);
    } catch (err: unknown) {
      const message =
        typeof err === "string" ? err : "標籤更新失敗，請稍後再試";
      showDialog({ type: "error", title: "更新失敗", message });
    }
  }, [draft, entityType, entityUid, setEntityTags, showDialog]);

  return (
    <div className="rounded-xl bg-card-bg p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xl font-semibold text-foreground">標籤</h2>
        {canEdit && !editing && (
          <Button size="sm" variant="secondary" onClick={handleStartEdit}>
            編輯標籤
          </Button>
        )}
      </div>

      {!editing && (
        <div className="flex flex-wrap items-center gap-2">
          {initialTags.length === 0 ? (
            <span className="text-sm text-muted">
              尚未為此 {ENTITY_LABEL[entityType]} 加上任何標籤
            </span>
          ) : (
            initialTags.map((t) => (
              <TagChip key={t.tag_uid} name={t.name} size="md" />
            ))
          )}
        </div>
      )}

      {editing && (
        <div className="flex flex-col gap-3">
          <TagInput
            value={draft}
            onChange={setDraft}
            disabled={isLoading}
          />
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={handleSave} disabled={isLoading}>
              {isLoading ? "儲存中..." : "儲存"}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={handleCancel}
              disabled={isLoading}
            >
              取消
            </Button>
          </div>
        </div>
      )}
    </div>
  );
});
