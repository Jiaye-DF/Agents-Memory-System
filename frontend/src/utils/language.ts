const EXT_TO_LANG: Record<string, string> = {
  js: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  jsx: "jsx",
  ts: "typescript",
  tsx: "tsx",
  py: "python",
  pyw: "python",
  rb: "ruby",
  php: "php",
  java: "java",
  kt: "kotlin",
  kts: "kotlin",
  swift: "swift",
  go: "go",
  rs: "rust",
  c: "c",
  h: "c",
  cpp: "cpp",
  cc: "cpp",
  cxx: "cpp",
  hpp: "cpp",
  cs: "csharp",
  sql: "sql",
  html: "markup",
  htm: "markup",
  xml: "markup",
  svg: "markup",
  vue: "markup",
  css: "css",
  scss: "scss",
  sass: "sass",
  less: "less",
  json: "json",
  jsonc: "json",
  yaml: "yaml",
  yml: "yaml",
  toml: "toml",
  ini: "ini",
  conf: "ini",
  md: "markdown",
  markdown: "markdown",
  mdx: "markdown",
  sh: "bash",
  bash: "bash",
  zsh: "bash",
  fish: "bash",
  ps1: "powershell",
  lua: "lua",
  r: "r",
  dart: "dart",
  scala: "scala",
  groovy: "groovy",
  gradle: "groovy",
  tf: "hcl",
  hcl: "hcl",
  graphql: "graphql",
  gql: "graphql",
  proto: "protobuf",
  env: "bash",
};

const FILENAME_TO_LANG: Record<string, string> = {
  dockerfile: "docker",
  makefile: "makefile",
  rakefile: "ruby",
  gemfile: "ruby",
  "package.json": "json",
  "tsconfig.json": "json",
};

export function detectLanguage(path: string): string {
  const filename = path.split(/[/\\]/).pop()?.toLowerCase() ?? "";

  if (FILENAME_TO_LANG[filename]) return FILENAME_TO_LANG[filename];
  if (filename.startsWith("dockerfile")) return "docker";
  if (filename.startsWith(".env")) return "bash";

  const lastDot = filename.lastIndexOf(".");
  if (lastDot === -1) return "text";
  const ext = filename.slice(lastDot + 1);
  return EXT_TO_LANG[ext] ?? "text";
}
