"use client";

import Link from "next/link";
import { useListAgentsQuery } from "@/store/agentsApi";
import { useListSkillsQuery } from "@/store/skillsApi";
import { PageLoading } from "@/components/ui/Loading";
import type { Agent, Skill } from "@/types";

function AgentMiniCard({ agent }: { agent: Agent }): React.ReactNode {
  return (
    <Link
      href={`/agents/${agent.agent_uid}`}
      className="flex flex-col gap-1.5 rounded-xl border border-border bg-card-bg p-4 transition-shadow hover:cursor-pointer hover:shadow-md"
    >
      <h3 className="truncate text-base font-semibold text-foreground">
        {agent.name}
      </h3>
      {agent.description && (
        <p className="line-clamp-2 text-sm text-muted">{agent.description}</p>
      )}
      <div className="flex flex-wrap gap-2 text-xs text-muted">
        {agent.language && <span>語言：{agent.language}</span>}
        {agent.model && <span>模型：{agent.model}</span>}
      </div>
    </Link>
  );
}

function SkillMiniCard({ skill }: { skill: Skill }): React.ReactNode {
  return (
    <Link
      href={`/skills/${skill.skill_uid}`}
      className="flex flex-col gap-1.5 rounded-xl border border-border bg-card-bg p-4 transition-shadow hover:cursor-pointer hover:shadow-md"
    >
      <h3 className="truncate text-base font-semibold text-foreground">
        {skill.name}
      </h3>
      <p className="line-clamp-2 text-sm text-muted">{skill.description}</p>
    </Link>
  );
}

export default function DashboardPage(): React.ReactNode {
  const { data: agentsData, isLoading: agentsLoading } = useListAgentsQuery({
    limit: 6,
  });
  const { data: skillsData, isLoading: skillsLoading } = useListSkillsQuery({
    limit: 6,
  });

  const publicAgents = (agentsData?.items ?? []).filter(
    (a) => a.visibility === "public"
  );
  const publicSkills = (skillsData?.items ?? []).filter(
    (s) => s.visibility === "public"
  );

  return (
    <div className="flex flex-col gap-8">
      <div>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-foreground">公開 Agents</h2>
          <Link
            href="/agents"
            className="text-sm text-primary hover:cursor-pointer hover:underline"
          >
            管理我的 Agents →
          </Link>
        </div>
        {agentsLoading ? (
          <PageLoading />
        ) : publicAgents.length === 0 ? (
          <div className="rounded-xl bg-card-bg p-8 text-center text-muted">
            目前沒有公開的 Agents
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {publicAgents.map((agent) => (
              <AgentMiniCard key={agent.agent_uid} agent={agent} />
            ))}
          </div>
        )}
      </div>

      <div>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-foreground">公開 Skills</h2>
          <Link
            href="/skills"
            className="text-sm text-primary hover:cursor-pointer hover:underline"
          >
            管理我的 Skills →
          </Link>
        </div>
        {skillsLoading ? (
          <PageLoading />
        ) : publicSkills.length === 0 ? (
          <div className="rounded-xl bg-card-bg p-8 text-center text-muted">
            目前沒有公開的 Skills
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {publicSkills.map((skill) => (
              <SkillMiniCard key={skill.skill_uid} skill={skill} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
