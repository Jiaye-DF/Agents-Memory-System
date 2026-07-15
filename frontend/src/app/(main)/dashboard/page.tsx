"use client";

import React, { useState, useMemo, useCallback } from "react";
import Link from "next/link";
import { useListAgentsQuery } from "@/store/agentsApi";
import {
  useListSkillsQuery,
  useSemanticSearchSkillsMutation,
} from "@/store/skillsApi";
import { useListScriptsQuery } from "@/store/scriptsApi";
import { useListAgentLanguagesQuery } from "@/store/agentLanguagesApi";
import { useDialog } from "@/hooks/useDialog";
import { PageLoading } from "@/components/ui/Loading";
import { FilterChip } from "@/components/ui/FilterChip";
import {
  SearchModeBar,
  type SearchMode,
} from "@/components/search/SearchModeBar";
import { RankingPanel } from "@/components/dashboard/RankingPanel";
import { SocialMetrics } from "@/components/social/SocialMetrics";
import { FavoriteButton } from "@/components/social/FavoriteButton";
import { TagList } from "@/components/tags";
import {
  parseSearch,
  matchByTextAndAuthor,
  toggleAuthorChip,
} from "@/utils/search";
import type { Agent, Skill, Script, SkillSearchResult } from "@/types";

type TabKey = "agents" | "skills" | "scripts" | "favorites";

type SortOrderBy = "created_at" | "download_count" | "favorite_count";
type SortOrder = "asc" | "desc";

interface SortState {
  orderBy: SortOrderBy;
  order: SortOrder;
}

interface SortGroup {
  prefix: string;
  orderBy: SortOrderBy;
  descLabel: string;
  ascLabel: string;
}

// §2-5 多軸排序：軸為前綴，chip 標籤用「由新到舊 / 由多到少」方向表述
const SORT_GROUPS: SortGroup[] = [
  {
    prefix: "按時間：",
    orderBy: "created_at",
    descLabel: "由新到舊",
    ascLabel: "由舊到新",
  },
  {
    prefix: "按收藏：",
    orderBy: "favorite_count",
    descLabel: "由多到少",
    ascLabel: "由少到多",
  },
  {
    prefix: "按熱度：",
    orderBy: "download_count",
    descLabel: "由多到少",
    ascLabel: "由少到多",
  },
];

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

const TabButton = React.memo(function TabButton({
  active,
  onClick,
  children,
}: TabButtonProps): React.ReactNode {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative px-4 py-2.5 text-base font-medium transition-colors hover:cursor-pointer ${
        active
          ? "text-primary"
          : "text-muted hover:text-foreground"
      }`}
    >
      {children}
      {active && (
        <span className="absolute inset-x-0 -bottom-px h-0.5 bg-primary" />
      )}
    </button>
  );
});

const AgentRow = React.memo(function AgentRow({
  agent,
  languageLabel,
}: {
  agent: Agent;
  languageLabel: string | null;
}): React.ReactNode {
  return (
    <div className="flex flex-col gap-2 px-4 py-3 transition-colors hover:bg-muted-bg/40 md:flex-row md:items-center md:gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <Link
            href={`/agents/${agent.agent_uid}`}
            className="min-w-0 truncate text-lg font-semibold text-foreground hover:cursor-pointer hover:text-primary hover:underline"
          >
            {agent.name}
          </Link>
          <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
            @{agent.owner_username ?? "未知"}
          </span>
        </div>
        {agent.description && (
          <p className="mt-1 line-clamp-1 text-base text-muted">
            {agent.description}
          </p>
        )}
        {agent.tags && agent.tags.length > 0 && (
          <div className="mt-1">
            <TagList tags={agent.tags} />
          </div>
        )}
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-3 text-sm text-muted md:ml-auto">
        {languageLabel && <span>語言：{languageLabel}</span>}
        {agent.model && <span>模型：{agent.model}</span>}
        <SocialMetrics
          favoriteCount={agent.favorite_count}
          downloadCount={agent.download_count}
        />
        <FavoriteButton
          resourceType="agent"
          resourceUid={agent.agent_uid}
          isFavorited={agent.is_favorited}
          size="sm"
        />
      </div>
    </div>
  );
});

const SkillRow = React.memo(function SkillRow({
  skill,
  isAiResult,
  aiReason,
}: {
  skill: Skill;
  isAiResult?: boolean;
  aiReason?: string | null;
}): React.ReactNode {
  return (
    <div className="flex flex-col gap-2 px-4 py-3 transition-colors hover:bg-muted-bg/40 md:flex-row md:items-center md:gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <Link
            href={`/skills/${skill.skill_uid}`}
            className="min-w-0 truncate text-lg font-semibold text-foreground hover:cursor-pointer hover:text-primary hover:underline"
          >
            {skill.name}
          </Link>
          <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
            @{skill.owner_username ?? "未知"}
          </span>
          {isAiResult && (
            <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
              AI 分析
            </span>
          )}
        </div>
        <p className="mt-1 line-clamp-1 text-base text-muted">
          {skill.description}
        </p>
        {aiReason && (
          <p className="mt-1 line-clamp-2 text-sm text-muted/80">{aiReason}</p>
        )}
        {skill.tags && skill.tags.length > 0 && (
          <div className="mt-1">
            <TagList tags={skill.tags} />
          </div>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-3 text-sm text-muted md:ml-auto">
        <SocialMetrics
          favoriteCount={skill.favorite_count}
          downloadCount={skill.download_count}
        />
        <FavoriteButton
          resourceType="skill"
          resourceUid={skill.skill_uid}
          isFavorited={skill.is_favorited}
          size="sm"
        />
      </div>
    </div>
  );
});

const ScriptRow = React.memo(function ScriptRow({
  script,
}: {
  script: Script;
}): React.ReactNode {
  return (
    <div className="flex flex-col gap-2 px-4 py-3 transition-colors hover:bg-muted-bg/40 md:flex-row md:items-center md:gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <Link
            href={`/scripts/${script.script_uid}`}
            className="min-w-0 truncate text-lg font-semibold text-foreground hover:cursor-pointer hover:text-primary hover:underline"
          >
            {script.name}
          </Link>
          <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
            @{script.owner_username ?? "未知"}
          </span>
        </div>
        {script.description && (
          <p className="mt-1 line-clamp-1 text-base text-muted">
            {script.description}
          </p>
        )}
        {script.tags && script.tags.length > 0 && (
          <div className="mt-1">
            <TagList tags={script.tags} />
          </div>
        )}
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-3 text-sm text-muted md:ml-auto">
        <span className="truncate">{script.file_name}</span>
        <SocialMetrics
          favoriteCount={script.favorite_count}
          downloadCount={script.download_count}
        />
        <FavoriteButton
          resourceType="script"
          resourceUid={script.script_uid}
          isFavorited={script.is_favorited}
          size="sm"
        />
      </div>
    </div>
  );
});

export default function DashboardPage(): React.ReactNode {
  const { showDialog } = useDialog();

  const [activeTab, setActiveTab] = useState<TabKey>("skills");
  const [query, setQuery] = useState<string>("");
  // v1.6.1：AI 分析僅作用於公開 Skills 頁籤，其他頁籤維持 keyword 過濾
  const [searchMode, setSearchMode] = useState<SearchMode>("keyword");
  const [aiResult, setAiResult] = useState<SkillSearchResult | null>(null);
  // chip 選的作者用獨立 state（避免含空白的 username 塞進 query 後被 \s+ 切壞）
  const [selectedAuthors, setSelectedAuthors] = useState<string[]>([]);
  // 公開市集的 tag filter：跨 user 用 tag name (lowercase) 識別；AND 邏輯
  const [selectedTagNames, setSelectedTagNames] = useState<string[]>([]);
  // §2-5：三頁籤共用 sort state；切換類型保留選擇；重新進頁面預設回「最新」
  const [sort, setSort] = useState<SortState>({
    orderBy: "created_at",
    order: "desc",
  });

  const { data: agentsData, isLoading: agentsLoading } = useListAgentsQuery({
    limit: 50,
    orderBy: sort.orderBy,
    order: sort.order,
  });
  const { data: skillsData, isLoading: skillsLoading } = useListSkillsQuery({
    limit: 50,
    orderBy: sort.orderBy,
    order: sort.order,
  });
  const { data: scriptsData, isLoading: scriptsLoading } = useListScriptsQuery({
    limit: 50,
    orderBy: sort.orderBy,
    order: sort.order,
  });
  const { data: languagesData } = useListAgentLanguagesQuery();
  const [semanticSearch, { isLoading: aiSearching }] =
    useSemanticSearchSkillsMutation();

  const languageNameMap = useMemo((): Map<string, string> => {
    const map = new Map<string, string>();
    for (const l of languagesData?.items ?? []) {
      map.set(l.code, l.name);
    }
    return map;
  }, [languagesData]);

  const resolveLanguage = useCallback(
    (code: string | null): string | null => {
      if (!code) return null;
      return languageNameMap.get(code) ?? code;
    },
    [languageNameMap]
  );

  // §2-4：公開 Scripts 資料源採「前端 filter」(沿用 useListScriptsQuery)；
  // 與 Agents / Skills 現行 pattern 對稱。後端 `/scripts/public` 端點已建立（§1-3），
  // 未來若資料量大再切換。
  const publicAgents = useMemo(
    (): Agent[] =>
      (agentsData?.items ?? []).filter((a) => a.visibility === "public"),
    [agentsData]
  );
  const publicSkills = useMemo(
    (): Skill[] =>
      (skillsData?.items ?? []).filter((s) => s.visibility === "public"),
    [skillsData]
  );
  const publicScripts = useMemo(
    (): Script[] =>
      (scriptsData?.items ?? []).filter((s) => s.visibility === "public"),
    [scriptsData]
  );

  const parsed = useMemo(() => parseSearch(query), [query]);

  const selectedAuthorsLower = useMemo(
    (): string[] => selectedAuthors.map((a) => a.toLowerCase()),
    [selectedAuthors]
  );

  const matchByTags = useCallback(
    (tags: { name: string }[] | undefined): boolean => {
      if (selectedTagNames.length === 0) return true;
      const have = new Set((tags ?? []).map((t) => t.name.toLowerCase()));
      return selectedTagNames.every((name) => have.has(name));
    },
    [selectedTagNames]
  );

  const filteredAgents = useMemo(
    (): Agent[] =>
      publicAgents.filter(
        (a) =>
          matchByTextAndAuthor(
            a.name,
            a.description,
            a.owner_username,
            parsed,
            selectedAuthorsLower
          ) && matchByTags(a.tags)
      ),
    [publicAgents, parsed, selectedAuthorsLower, matchByTags]
  );
  const filteredSkills = useMemo(
    (): Skill[] =>
      publicSkills.filter(
        (s) =>
          matchByTextAndAuthor(
            s.name,
            s.description,
            s.owner_username,
            parsed,
            selectedAuthorsLower
          ) && matchByTags(s.tags)
      ),
    [publicSkills, parsed, selectedAuthorsLower, matchByTags]
  );
  const filteredScripts = useMemo(
    (): Script[] =>
      publicScripts.filter(
        (s) =>
          matchByTextAndAuthor(
            s.name,
            s.description,
            s.owner_username,
            parsed,
            selectedAuthorsLower
          ) && matchByTags(s.tags)
      ),
    [publicScripts, parsed, selectedAuthorsLower, matchByTags]
  );

  const currentAuthors = useMemo((): string[] => {
    let items: { owner_username: string | null }[] = [];
    if (activeTab === "agents") items = publicAgents;
    else if (activeTab === "skills") items = publicSkills;
    else items = publicScripts;
    const set = new Set<string>();
    for (const it of items) {
      if (it.owner_username) set.add(it.owner_username);
    }
    return Array.from(set).sort();
  }, [activeTab, publicAgents, publicSkills, publicScripts]);

  // 公開市集跨 user 共用 tag 池：以 lowercase name 去重，顯示用首次出現的原樣 name
  const currentTags = useMemo((): { name: string; display: string }[] => {
    let items: { tags?: { tag_uid: string; name: string }[] }[] = [];
    if (activeTab === "agents") items = publicAgents;
    else if (activeTab === "skills") items = publicSkills;
    else items = publicScripts;
    const seen = new Map<string, string>();
    for (const it of items) {
      for (const t of it.tags ?? []) {
        const lower = t.name.toLowerCase();
        if (!seen.has(lower)) seen.set(lower, t.name);
      }
    }
    return Array.from(seen.entries())
      .map(([name, display]) => ({ name, display }))
      .sort((a, b) => a.display.localeCompare(b.display));
  }, [activeTab, publicAgents, publicSkills, publicScripts]);

  const handleQueryChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setQuery(e.target.value);
    },
    []
  );

  const handleToggleAuthor = useCallback((author: string): void => {
    setSelectedAuthors((prev) => toggleAuthorChip(prev, author));
  }, []);

  const handleToggleTag = useCallback((lowerName: string): void => {
    setSelectedTagNames((prev) =>
      prev.includes(lowerName)
        ? prev.filter((n) => n !== lowerName)
        : [...prev, lowerName]
    );
  }, []);

  const handleTabChange = useCallback((tab: TabKey): void => {
    setActiveTab(tab);
    setAiResult(null);
  }, []);

  const handleModeChange = useCallback((mode: SearchMode): void => {
    setSearchMode(mode);
    if (mode === "keyword") setAiResult(null);
  }, []);

  const isAiMode = activeTab === "skills" && searchMode === "ai";

  const handleSearchSubmit = useCallback(
    (e: React.FormEvent<HTMLFormElement>): void => {
      e.preventDefault();
      if (!isAiMode) return;
      const trimmed = query.trim();
      if (trimmed.length === 0) return;
      void (async (): Promise<void> => {
        try {
          const result = await semanticSearch({
            query: trimmed,
            scope: "public",
          }).unwrap();
          setAiResult(result);
        } catch (err: unknown) {
          const fallback = "AI 分析失敗，請稍後再試";
          const message = typeof err === "string" ? err : fallback;
          showDialog({ type: "error", title: "AI 分析失敗", message });
        }
      })();
    },
    [isAiMode, query, semanticSearch, showDialog]
  );

  const handleSortChange = useCallback(
    (orderBy: SortOrderBy, order: SortOrder): void => {
      setSort({ orderBy, order });
    },
    []
  );

  const isLoading =
    activeTab === "agents"
      ? agentsLoading
      : activeTab === "skills"
        ? skillsLoading
        : scriptsLoading;
  const totalCount =
    activeTab === "agents"
      ? publicAgents.length
      : activeTab === "skills"
        ? publicSkills.length
        : publicScripts.length;
  const filteredCount =
    activeTab === "agents"
      ? filteredAgents.length
      : activeTab === "skills"
        ? filteredSkills.length
        : filteredScripts.length;
  const manageHref =
    activeTab === "agents"
      ? "/agents"
      : activeTab === "skills"
        ? "/skills"
        : "/scripts";
  const manageLabel =
    activeTab === "agents"
      ? "Agents"
      : activeTab === "skills"
        ? "Skills"
        : "Scripts";

  const isFavoritesTab = activeTab === "favorites";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1 border-b border-border">
        <TabButton
          active={activeTab === "skills"}
          onClick={() => handleTabChange("skills")}
        >
          公開 Skills ({publicSkills.length})
        </TabButton>
        <TabButton
          active={activeTab === "agents"}
          onClick={() => handleTabChange("agents")}
        >
          公開 Agents ({publicAgents.length})
        </TabButton>
        <TabButton
          active={activeTab === "scripts"}
          onClick={() => handleTabChange("scripts")}
        >
          公開 Scripts ({publicScripts.length})
        </TabButton>
        <TabButton
          active={isFavoritesTab}
          onClick={() => handleTabChange("favorites")}
        >
          最常使用
        </TabButton>
        {!isFavoritesTab && (
          <Link
            href={manageHref}
            className="ml-auto text-base text-primary hover:cursor-pointer hover:underline"
          >
            管理我的 {manageLabel} →
          </Link>
        )}
      </div>

      {isFavoritesTab ? (
        <RankingPanel />
      ) : (
        <>

      {/* v1.6 UI 調整：模式選擇器內建於搜尋框左側；僅公開 Skills 頁籤顯示，其他頁籤鎖定 keyword */}
      <SearchModeBar
        mode={activeTab === "skills" ? searchMode : "keyword"}
        onModeChange={handleModeChange}
        value={query}
        onChange={handleQueryChange}
        onSubmit={handleSearchSubmit}
        isLoading={aiSearching}
        showModeSelect={activeTab === "skills"}
        placeholder={
          isAiMode
            ? "用一句話描述你要找的 Skill…"
            : "搜尋名稱、描述，或輸入 @作者 篩選（可多個）"
        }
      />

      {!isAiMode && currentAuthors.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="shrink-0 text-sm text-muted">作者：</span>
          {currentAuthors.map((author) => {
            const lower = author.toLowerCase();
            const isSelected =
              parsed.authors.includes(lower) ||
              selectedAuthorsLower.includes(lower);
            return (
              <button
                key={author}
                type="button"
                onClick={() => handleToggleAuthor(author)}
                className={`rounded-xl px-3 py-1 text-sm font-medium transition-colors hover:cursor-pointer ${
                  isSelected
                    ? "bg-primary text-white"
                    : "bg-muted-bg text-muted hover:bg-border"
                }`}
              >
                @{author}
              </button>
            );
          })}
        </div>
      )}

      {!isAiMode && currentTags.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="shrink-0 text-sm text-muted">標籤：</span>
          {currentTags.map((t) => {
            const isSelected = selectedTagNames.includes(t.name);
            return (
              <button
                key={t.name}
                type="button"
                onClick={() => handleToggleTag(t.name)}
                className={`rounded-xl px-3 py-1 text-sm font-medium transition-colors hover:cursor-pointer ${
                  isSelected
                    ? "bg-primary text-white"
                    : "bg-muted-bg text-muted hover:bg-border"
                }`}
              >
                {t.display}
              </button>
            );
          })}
          {selectedTagNames.length > 0 && (
            <button
              type="button"
              onClick={() => setSelectedTagNames([])}
              className="ml-1 text-xs text-muted hover:cursor-pointer hover:text-foreground hover:underline"
            >
              清除
            </button>
          )}
        </div>
      )}

      {!isAiMode && (
      <div className="flex flex-col gap-2 md:flex-row md:flex-wrap md:items-center md:gap-x-6">
        {SORT_GROUPS.map((group) => (
          <div
            key={group.orderBy}
            className="flex flex-wrap items-center gap-2"
          >
            <span className="shrink-0 text-sm text-muted">{group.prefix}</span>
            <FilterChip
              active={sort.orderBy === group.orderBy && sort.order === "desc"}
              onClick={() => handleSortChange(group.orderBy, "desc")}
            >
              {group.descLabel}
            </FilterChip>
            <FilterChip
              active={sort.orderBy === group.orderBy && sort.order === "asc"}
              onClick={() => handleSortChange(group.orderBy, "asc")}
            >
              {group.ascLabel}
            </FilterChip>
          </div>
        ))}
      </div>
      )}

      {isAiMode ? (
        aiSearching ? (
          <PageLoading />
        ) : aiResult === null ? (
          <div className="rounded-xl bg-card-bg p-8 text-center text-muted">
            輸入需求描述後按「AI 分析」開始語意檢索。
          </div>
        ) : aiResult.items.length === 0 ? (
          <div className="rounded-xl bg-card-bg p-8 text-center text-muted">
            找不到語意相近的 Skill
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl bg-card-bg shadow-sm">
            {aiResult.analysis && (
              <div className="border-b border-border px-4 py-3 text-sm text-muted">
                {aiResult.analysis}
              </div>
            )}
            <div className="divide-y divide-border">
              {aiResult.items.map((item) => (
                <SkillRow
                  key={item.skill_uid}
                  skill={item}
                  isAiResult
                  aiReason={item.ai_reason}
                />
              ))}
            </div>
          </div>
        )
      ) : isLoading ? (
        <PageLoading />
      ) : totalCount === 0 ? (
        <div className="rounded-xl bg-card-bg p-8 text-center text-muted">
          目前沒有公開的 {manageLabel}
        </div>
      ) : filteredCount === 0 ? (
        <div className="rounded-xl bg-card-bg p-8 text-center text-muted">
          沒有符合條件的 {manageLabel}
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl bg-card-bg shadow-sm">
          <div className="divide-y divide-border">
            {activeTab === "agents" &&
              filteredAgents.map((agent) => (
                <AgentRow
                  key={agent.agent_uid}
                  agent={agent}
                  languageLabel={resolveLanguage(agent.language)}
                />
              ))}
            {activeTab === "skills" &&
              filteredSkills.map((skill) => (
                <SkillRow key={skill.skill_uid} skill={skill} />
              ))}
            {activeTab === "scripts" &&
              filteredScripts.map((script) => (
                <ScriptRow key={script.script_uid} script={script} />
              ))}
          </div>
        </div>
      )}

        </>
      )}
    </div>
  );
}
