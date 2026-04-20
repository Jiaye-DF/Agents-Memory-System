export interface ComposePromptInput {
  identity?: string | null;
  languageName?: string | null;
  style?: string | null;
  role_prompt?: string | null;
}

/**
 * 依照後端服務層的組裝順序，組出使用者最終看到的 System Prompt。
 * 順序：identity → language → style → role_prompt
 * 空欄位會被略過，不會出現空段。
 */
export function composeSystemPrompt(input: ComposePromptInput): string {
  const parts: string[] = [];

  const identity = (input.identity ?? "").trim();
  if (identity) {
    parts.push(`你的身分：${identity}`);
  }

  const language = (input.languageName ?? "").trim();
  if (language) {
    parts.push(`請使用 ${language} 回覆使用者。`);
  }

  const style = (input.style ?? "").trim();
  if (style) {
    parts.push(`回覆風格：${style}`);
  }

  const rolePrompt = (input.role_prompt ?? "").trim();
  if (rolePrompt) {
    parts.push(rolePrompt);
  }

  return parts.join("\n\n");
}
