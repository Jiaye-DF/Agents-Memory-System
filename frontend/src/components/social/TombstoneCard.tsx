"use client";

import React, { useCallback } from "react";
import { Button } from "@/components/ui/Button";
import type { ResourceType } from "@/types";

interface TombstoneCardProps {
  resourceType: ResourceType;
  resourceUid: string;
  onRemove: (resourceUid: string) => void;
  isRemoving?: boolean;
}

const TYPE_LABEL: Record<ResourceType, string> = {
  agent: "Agent",
  skill: "Skill",
  script: "Script",
};

export const TombstoneCard = React.memo(function TombstoneCard({
  resourceType,
  resourceUid,
  onRemove,
  isRemoving = false,
}: TombstoneCardProps): React.ReactNode {
  const handleRemove = useCallback((): void => {
    onRemove(resourceUid);
  }, [resourceUid, onRemove]);

  return (
    <div className="flex flex-col gap-3 bg-muted-bg px-4 py-4 transition-colors md:flex-row md:items-center md:gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span aria-hidden className="text-lg text-warning">
            ⚠
          </span>
          <h3 className="truncate text-lg font-semibold text-muted">
            此 {TYPE_LABEL[resourceType]} 已被移除
          </h3>
        </div>
        <p className="mt-1 text-base text-muted">
          原始資源已被擁有者刪除或不再可見，可從收藏清單移除此項。
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-2 md:ml-auto">
        <Button
          size="sm"
          variant="secondary"
          onClick={handleRemove}
          loading={isRemoving}
        >
          從收藏移除
        </Button>
      </div>
    </div>
  );
});
