export function validateAccount(account: string): string | null {
  if (!account) return "帳號為必填欄位";
  if (account.length < 8) return "帳號長度至少 8 個字元";
  if (!/[a-zA-Z]/.test(account)) return "帳號須包含至少一個英文字母";
  if (!/[0-9]/.test(account)) return "帳號須包含至少一個數字";
  return null;
}

export function validatePassword(password: string): string | null {
  if (!password) return "密碼為必填欄位";
  if (password.length < 8) return "密碼長度至少 8 個字元";
  if (!/[a-z]/.test(password)) return "密碼須包含至少一個小寫字母";
  if (!/[A-Z]/.test(password)) return "密碼須包含至少一個大寫字母";
  if (!/[0-9]/.test(password)) return "密碼須包含至少一個數字";
  return null;
}

export function validateUsername(username: string): string | null {
  if (!username) return "使用者名稱為必填欄位";
  if (username.length < 2) return "使用者名稱長度至少 2 個字元";
  if (username.length > 50) return "使用者名稱長度不得超過 50 個字元";
  return null;
}

export function validateConfirmPassword(
  password: string,
  confirmPassword: string
): string | null {
  if (!confirmPassword) return "確認密碼為必填欄位";
  if (password !== confirmPassword) return "確認密碼與密碼不一致";
  return null;
}

export type PasswordStrength = "weak" | "medium" | "strong";

export function getPasswordStrength(password: string): PasswordStrength {
  if (!password || password.length < 8) return "weak";

  let score = 0;
  if (/[a-z]/.test(password)) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^a-zA-Z0-9]/.test(password)) score++;
  if (password.length >= 12) score++;

  if (score >= 4) return "strong";
  if (score >= 3) return "medium";
  return "weak";
}
