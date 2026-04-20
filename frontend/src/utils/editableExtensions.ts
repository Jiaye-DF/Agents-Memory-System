export const EDITABLE_EXTENSIONS = new Set<string>([
  ".md",
  ".txt",
  ".json",
  ".yaml",
  ".yml",
  ".py",
  ".ts",
  ".js",
  ".sh",
]);

export const FILE_EDIT_MAX_BYTES = 500 * 1024;

export function isEditable(filename: string): boolean {
  const idx = filename.lastIndexOf(".");
  if (idx < 0) return false;
  return EDITABLE_EXTENSIONS.has(filename.slice(idx).toLowerCase());
}
