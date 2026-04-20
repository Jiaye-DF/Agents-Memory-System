"use client";

import React, { Suspense } from "react";
import { PageLoading } from "@/components/ui/Loading";
import { AgentForm } from "../_components/AgentForm";

export default function AgentNewPage(): React.ReactNode {
  return (
    <Suspense fallback={<PageLoading />}>
      <AgentForm mode="create" />
    </Suspense>
  );
}
