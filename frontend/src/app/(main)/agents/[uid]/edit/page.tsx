"use client";

import React, { Suspense } from "react";
import { useParams } from "next/navigation";
import { PageLoading } from "@/components/ui/Loading";
import { useGetAgentQuery } from "@/store/agentsApi";
import { AgentForm } from "../../_components/AgentForm";

function AgentEditContent({ agentUid }: { agentUid: string }): React.ReactNode {
  const { data: agent, isLoading } = useGetAgentQuery(agentUid);

  if (isLoading) {
    return <PageLoading />;
  }

  if (!agent) {
    return (
      <div className="py-12 text-center text-muted">找不到指定的 Agent</div>
    );
  }

  return <AgentForm mode="edit" agent={agent} />;
}

export default function AgentEditPage(): React.ReactNode {
  const params = useParams<{ uid: string }>();
  const agentUid = params.uid;

  return (
    <Suspense fallback={<PageLoading />}>
      <AgentEditContent agentUid={agentUid} />
    </Suspense>
  );
}
