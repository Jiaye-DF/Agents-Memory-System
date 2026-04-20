"use client";

import React, { useState, useMemo, useCallback } from "react";
import Link from "next/link";
import { useListAgentsQuery } from "@/store/agentsApi";
import { useListSkillsQuery } from "@/store/skillsApi";
import { useListAgentLanguagesQuery } from "@/store/agentLanguagesApi";
import { PageLoading } from "@/components/ui/Loading";
import { Input } from "@/components/ui/Input";
import type { Agent, Skill } from "@/types";

type TabKey = "agents" | "skills";

interface ParsedSearch {
  text: string;
  authors: string[];
}

function parseSearch(query: string): ParsedSearch {
  const tokens = query.trim().split(/\s+/).filter(Boolean);
  const authors: string[] = [];
  const words: string[] = [];
  for (const token of tokens) {
    if (token.startsWith("@") && token.length > 1) {
      authors.push(token.slice(1).toLowerCase());
    } else {
      words.push(token);
    }
  }
  return { text: words.join(" ").toLowerCase(), authors };
}

function matchItem(
  name: string,
  description: string | null,
  author: string | null,
  parsed: ParsedSearch
): boolean {
  if (parsed.authors.length > 0) {
    const authorLower = (author ?? "").toLowerCase();
    if (!parsed.authors.includes(authorLower)) return false;
  }
  if (!parsed.text) return true;
  const haystack = `${name} ${description ?? ""}`.toLowerCase();
  return haystack.includes(parsed.text);
}

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
    <Link
      href={`/agents/${agent.agent_uid}`}
      className="flex flex-col gap-2 px-4 py-3 transition-colors hover:cursor-pointer hover:bg-muted-bg/40 md:flex-row md:items-center md:gap-4"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h3 className="truncate text-lg font-semibold text-foreground">
            {agent.name}
          </h3>
          <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
            @{agent.owner_username ?? "未知"}
          </span>
        </div>
        {agent.description && (
          <p className="mt-1 line-clamp-1 text-base text-muted">
            {agent.description}
          </p>
        )}
      </div>
      <div className="flex shrink-0 flex-wrap gap-2 text-sm text-muted md:ml-auto">
        {languageLabel && <span>語言：{languageLabel}</span>}
        {agent.model && <span>模型：{agent.model}</span>}
      </div>
    </Link>
  );
});

const SkillRow = React.memo(function SkillRow({
  skill,
}: {
  skill: Skill;
}): React.ReactNode {
  return (
    <Link
      href={`/skills/${skill.skill_uid}`}
      className="flex flex-col gap-2 px-4 py-3 transition-colors hover:cursor-pointer hover:bg-muted-bg/40 md:flex-row md:items-center md:gap-4"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h3 className="truncate text-lg font-semibold text-foreground">
            {skill.name}
          </h3>
          <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
            @{skill.owner_username ?? "未知"}
          </span>
        </div>
        <p className="mt-1 line-clamp-1 text-base text-muted">
          {skill.description}
        </p>
      </div>
    </Link>
  );
});

export default function DashboardPage(): React.ReactNode {
  const [activeTab, setActiveTab] = useState<TabKey>("agents");
  const [query, setQuery] = useState<string>("");

  const { data: agentsData, isLoading: agentsLoading } = useListAgentsQuery({
    limit: 50,
  });
  const { data: skillsData, isLoading: skillsLoading } = useListSkillsQuery({
    limit: 50,
  });
  const { data: languagesData } = useListAgentLanguagesQuery();

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

  const parsed = useMemo(() => parseSearch(query), [query]);

  const filteredAgents = useMemo(
    (): Agent[] =>
      publicAgents.filter((a) =>
        matchItem(a.name, a.description, a.owner_username, parsed)
      ),
    [publicAgents, parsed]
  );
  const filteredSkills = useMemo(
    (): Skill[] =>
      publicSkills.filter((s) =>
        matchItem(s.name, s.description, s.owner_username, parsed)
      ),
    [publicSkills, parsed]
  );

  const currentAuthors = useMemo((): string[] => {
    const items = activeTab === "agents" ? publicAgents : publicSkills;
    const set = new Set<string>();
    for (const it of items) {
      const name =
        activeTab === "agents"
          ? (it as Agent).owner_username
          : (it as Skill).owner_username;
      if (name) set.add(name);
    }
    return Array.from(set).sort();
  }, [activeTab, publicAgents, publicSkills]);

  const handleQueryChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setQuery(e.target.value);
    },
    []
  );

  const toggleAuthorChip = useCallback(
    (author: string): void => {
      const tokens = query.trim().split(/\s+/).filter(Boolean);
      const target = `@${author}`.toLowerCase();
      const idx = tokens.findIndex((t) => t.toLowerCase() === target);
      if (idx >= 0) {
        tokens.splice(idx, 1);
      } else {
        tokens.push(`@${author}`);
      }
      setQuery(tokens.join(" "));
    },
    [query]
  );

  const handleTabChange = useCallback((tab: TabKey): void => {
    setActiveTab(tab);
  }, []);

  const showAgents = activeTab === "agents";
  const isLoading = showAgents ? agentsLoading : skillsLoading;
  const totalCount = showAgents ? publicAgents.length : publicSkills.length;
  const filteredCount = showAgents
    ? filteredAgents.length
    : filteredSkills.length;
  const manageHref = showAgents ? "/agents" : "/skills";
  const manageLabel = showAgents ? "Agents" : "Skills";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1 border-b border-border">
        <TabButton
          active={activeTab === "agents"}
          onClick={() => handleTabChange("agents")}
        >
          公開 Agents ({publicAgents.length})
        </TabButton>
        <TabButton
          active={activeTab === "skills"}
          onClick={() => handleTabChange("skills")}
        >
          公開 Skills ({publicSkills.length})
        </TabButton>
        <Link
          href={manageHref}
          className="ml-auto text-base text-primary hover:cursor-pointer hover:underline"
        >
          管理我的 {manageLabel} →
        </Link>
      </div>

      <Input
        placeholder="搜尋名稱、描述，或輸入 @作者 篩選（可多個）"
        value={query}
        onChange={handleQueryChange}
      />

      {currentAuthors.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="shrink-0 text-sm text-muted">作者：</span>
          {currentAuthors.map((author) => {
            const isSelected = parsed.authors.includes(author.toLowerCase());
            return (
              <button
                key={author}
                type="button"
                onClick={() => toggleAuthorChip(author)}
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

      {isLoading ? (
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
            {showAgents
              ? filteredAgents.map((agent) => (
                  <AgentRow
                    key={agent.agent_uid}
                    agent={agent}
                    languageLabel={resolveLanguage(agent.language)}
                  />
                ))
              : filteredSkills.map((skill) => (
                  <SkillRow key={skill.skill_uid} skill={skill} />
                ))}
          </div>
        </div>
      )}
    </div>
  );
}
