#!/usr/bin/env node

import { lstat, readdir, readFile } from "node:fs/promises";
import { dirname, extname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const showcaseRoot = join(repositoryRoot, "apps", "showcase");
const outputRoot = join(showcaseRoot, "out");
const publicRoot = join(showcaseRoot, "public");
const vercelConfigPath = join(repositoryRoot, "vercel.json");

const DISCLOSURE_ATTRIBUTE = "data-public-demo-disclosure";
const DISCLOSURE_TEXT =
  "Public portfolio demo with synthetic data. No uploads, persistence, live AI, or real-world actions.";

const PUBLIC_DEMO_IDS = Object.freeze({
  documents: Object.freeze([
    "11111111-1111-4111-8111-111111111111",
    "12121212-1212-4121-8121-121212121212",
    "13131313-1313-4131-8131-131313131313",
  ]),
  approval: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  tasks: Object.freeze([
    "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "d1d1d1d1-d1d1-4d1d-8d1d-d1d1d1d1d1d1",
  ]),
  evaluation: "20260830T091500000000Z-deterministic-showcase",
  auditEvents: Object.freeze([
    "e1111111-1111-4111-8111-111111111111",
    "e2222222-2222-4222-8222-222222222222",
    "e3333333-3333-4333-8333-333333333333",
    "e4444444-4444-4444-8444-444444444444",
    "e5555555-5555-4555-8555-555555555555",
  ]),
});

const PUBLIC_ROUTE_PATHS = Object.freeze([
  "/",
  "/login/",
  "/overview/",
  "/documents/",
  ...PUBLIC_DEMO_IDS.documents.map((documentId) => `/documents/${documentId}/`),
  "/ask/",
  "/approvals/",
  `/approvals/${PUBLIC_DEMO_IDS.approval}/`,
  "/tasks/",
  ...PUBLIC_DEMO_IDS.tasks.map((taskId) => `/tasks/${taskId}/`),
  "/evaluations/",
  `/evaluations/${PUBLIC_DEMO_IDS.evaluation}/`,
  "/audit/",
  ...PUBLIC_DEMO_IDS.auditEvents.map((eventId) => `/audit/${eventId}/`),
]);

const REQUIRED_HTML_FILES = new Map([
  ...PUBLIC_ROUTE_PATHS.map((route) => [route, routeToHtmlFile(route)]),
  ["404", "404.html"],
  ["404 trailing-slash alias", "404/index.html"],
  ["Next not-found alias", "_not-found/index.html"],
]);

const FORBIDDEN_OUTPUT_PATHS = Object.freeze([
  { label: "source map", pattern: /(?:^|\/)\S+\.map$/iu },
  { label: "API directory", pattern: /(?:^|\/)api(?:\/|$)/iu },
  { label: "server directory", pattern: /(?:^|\/)server(?:\/|$)/iu },
  {
    label: "function bundle",
    pattern: /(?:^|\/)(?:functions?|_functions)(?:\/|$)/iu,
  },
  { label: "Next build directory", pattern: /(?:^|\/)\.next(?:\/|$)/iu },
  {
    label: "server manifest",
    pattern:
      /(?:^|\/)(?:app-paths-manifest|build-manifest|middleware-manifest|pages-manifest|prerender-manifest|required-server-files|routes-manifest|server-reference-manifest)\.(?:js|json)$/iu,
  },
  { label: "server trace", pattern: /(?:^|\/)(?:trace|trace-build)$/iu },
  { label: "Node file trace", pattern: /\.nft\.json$/iu },
  { label: "environment file", pattern: /(?:^|\/)\.env(?:\.|$)/iu },
  { label: "private key material", pattern: /\.(?:key|p12|pfx|pem)$/iu },
  { label: "source file", pattern: /\.(?:cjs|cts|jsx|mjs|mts|ts|tsx)$/iu },
]);

const FORBIDDEN_BYTES = Object.freeze([
  {
    label: "localhost URL",
    pattern:
      /\b(?:https?|wss?):(?:\/\/|\\u002f\\u002f|%2f%2f)localhost(?::\d{1,5})?(?:[/?#"'`]|$)/iu,
  },
  { label: "IPv4 loopback address", pattern: /\b127(?:\.\d{1,3}){3}\b/u },
  { label: "unspecified listen address", pattern: /\b0\.0\.0\.0\b/u },
  { label: "RFC1918 10/8 address", pattern: /\b10(?:\.\d{1,3}){3}\b/u },
  {
    label: "RFC1918 172.16/12 address",
    pattern: /\b172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}\b/u,
  },
  {
    label: "RFC1918 192.168/16 address",
    pattern: /\b192\.168(?:\.\d{1,3}){2}\b/u,
  },
  { label: "link-local address", pattern: /\b169\.254(?:\.\d{1,3}){2}\b/u },
  { label: "Docker host alias", pattern: /\bhost\.docker\.internal\b/iu },
  { label: "private API environment name", pattern: /\bAPI_INTERNAL_URL\b/u },
  {
    label: "browser API environment name",
    pattern: /\bNEXT_PUBLIC_API_URL\b/u,
  },
  { label: "WebSocket URL", pattern: /\bwss?:\/\/[\w.[\]:%-]+/iu },
  {
    label: "webhook URL",
    pattern: /\bhttps?:\/\/[^\s"'`<>)]*\/[^\s"'`<>)]*webhooks?(?:[/?#]|\b)/iu,
  },
  {
    label: "personal Windows user path",
    pattern: /\b[a-z]:[\\/]users[\\/][^\\/\s"'`<>]+/iu,
  },
  {
    label: "personal OneDrive path",
    pattern: /\bOneDrive\s*-\s*ku\.ac\.ae\b/iu,
  },
  {
    label: "environment filename",
    pattern: /(?:^|[\\/])\.env(?:\.|[\\/\s"'`]|$)/iu,
  },
  {
    label: "private key block",
    pattern: /-----BEGIN [A-Z ]*PRIVATE KEY-----/u,
  },
  { label: "AWS access key", pattern: /\bAKIA[0-9A-Z]{16}\b/u },
  { label: "GitHub access token", pattern: /\bgh[pousr]_[A-Za-z0-9]{30,}\b/u },
  { label: "OpenAI-style secret", pattern: /\bsk-[A-Za-z0-9_-]{20,}\b/u },
  {
    label: "JSON Web Token",
    pattern: /\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/u,
  },
  {
    label: "assigned secret value",
    pattern:
      /\b(?:api[_-]?key|client[_-]?secret|password|private[_-]?key|refresh[_-]?token)\b\s*[:=]\s*["'`][^"'`\s]{8,}/iu,
  },
  {
    label: "unexpected API target",
    pattern: /(?:["'`(=]|\\u0022|\\x22)\/api(?:\/|[?#["'`)]|\\u002f)/iu,
  },
]);

const NEXT_STATIC_EXTENSIONS = new Set([
  ".avif",
  ".css",
  ".gif",
  ".ico",
  ".jpeg",
  ".jpg",
  ".js",
  ".png",
  ".svg",
  ".webp",
  ".woff",
  ".woff2",
]);

const ROUTE_PAYLOAD_EXTENSIONS = new Set([".rsc", ".txt"]);

const REQUIRED_VERCEL_HEADERS = Object.freeze({
  "Content-Security-Policy":
    "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; frame-src 'none'; form-action 'none'; script-src 'self' 'unsafe-inline'; script-src-attr 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; media-src 'self'; connect-src 'self'; worker-src 'self' blob:; manifest-src 'self'; upgrade-insecure-requests",
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Resource-Policy": "same-origin",
  "Permissions-Policy":
    "accelerometer=(), autoplay=(), camera=(), display-capture=(), encrypted-media=(), fullscreen=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), publickey-credentials-get=(), usb=()",
  "Referrer-Policy": "no-referrer",
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
  "X-Content-Type-Options": "nosniff",
  "X-DNS-Prefetch-Control": "off",
  "X-Frame-Options": "DENY",
});

function routeToHtmlFile(route) {
  if (route === "/") {
    return "index.html";
  }

  return `${route.replace(/^\//u, "").replace(/\/$/u, "")}/index.html`;
}

function toPortablePath(value) {
  return value.split(sep).join("/");
}

async function walkFiles(root) {
  const rootStats = await lstat(root).catch(() => null);
  if (!rootStats?.isDirectory()) {
    throw new Error(`Required directory does not exist: ${root}`);
  }

  const files = [];
  const pending = [root];

  while (pending.length > 0) {
    const current = pending.pop();
    const entries = await readdir(current, { withFileTypes: true });

    for (const entry of entries) {
      const absolutePath = join(current, entry.name);
      const portablePath = toPortablePath(relative(root, absolutePath));

      if (entry.isSymbolicLink()) {
        throw new Error(
          `Symbolic links are not allowed in the public artifact: ${portablePath}`,
        );
      }

      if (entry.isDirectory()) {
        pending.push(absolutePath);
        continue;
      }

      if (!entry.isFile()) {
        throw new Error(
          `Unsupported filesystem entry in the public artifact: ${portablePath}`,
        );
      }

      const stats = await lstat(absolutePath);
      files.push({ absolutePath, path: portablePath, bytes: stats.size });
    }
  }

  return files.sort((left, right) => left.path.localeCompare(right.path));
}

function routeArtifactRoots() {
  return PUBLIC_ROUTE_PATHS.map((route) => {
    if (route === "/") {
      return "";
    }

    return route.replace(/^\//u, "").replace(/\/$/u, "");
  });
}

function isExpectedRoutePayload(filePath) {
  const extension = extname(filePath).toLowerCase();
  if (!ROUTE_PAYLOAD_EXTENSIONS.has(extension)) {
    return false;
  }

  const routeRoots = routeArtifactRoots();
  return routeRoots.some((root) => {
    if (root === "") {
      return !filePath.includes("/");
    }

    return (
      filePath === `${root}${extension}` || filePath.startsWith(`${root}/`)
    );
  });
}

function assertAllowedPath(filePath, publicFiles) {
  if ([...REQUIRED_HTML_FILES.values()].includes(filePath)) {
    return;
  }

  if (publicFiles.has(filePath)) {
    return;
  }

  if (filePath === "icon.svg") {
    return;
  }

  if (
    filePath.startsWith("_not-found/") &&
    ROUTE_PAYLOAD_EXTENSIONS.has(extname(filePath).toLowerCase())
  ) {
    return;
  }

  if (filePath.startsWith("_next/static/")) {
    const extension = extname(filePath).toLowerCase();
    if (NEXT_STATIC_EXTENSIONS.has(extension)) {
      return;
    }
  }

  if (isExpectedRoutePayload(filePath)) {
    return;
  }

  throw new Error(`Unexpected file outside the static allowlist: ${filePath}`);
}

function findForbiddenPath(filePath) {
  return FORBIDDEN_OUTPUT_PATHS.find(({ pattern }) => pattern.test(filePath));
}

function findForbiddenBytes(buffer) {
  const contents = buffer.toString("latin1");
  return FORBIDDEN_BYTES.find(({ pattern }) => pattern.test(contents));
}

async function loadPublicFileAllowlist() {
  const publicStats = await lstat(publicRoot).catch(() => null);
  if (!publicStats) {
    return new Set();
  }

  const publicFiles = await walkFiles(publicRoot);
  return new Set(publicFiles.map((file) => file.path));
}

function summarizeByExtension(files) {
  const totals = new Map();

  for (const file of files) {
    const extension = extname(file.path).toLowerCase() || "[none]";
    const current = totals.get(extension) ?? { files: 0, bytes: 0 };
    current.files += 1;
    current.bytes += file.bytes;
    totals.set(extension, current);
  }

  return Object.fromEntries(
    [...totals.entries()].sort(([left], [right]) => left.localeCompare(right)),
  );
}

async function verifyVercelConfiguration(failures) {
  let config;
  try {
    config = JSON.parse(await readFile(vercelConfigPath, "utf8"));
  } catch (error) {
    failures.push(`vercel.json is missing or invalid: ${error.message}`);
    return { headers: [], status: "invalid" };
  }

  const requiredFields = {
    buildCommand: "npm run build:showcase",
    framework: null,
    outputDirectory: "apps/showcase/out",
    trailingSlash: true,
  };
  for (const [field, expectedValue] of Object.entries(requiredFields)) {
    if (config[field] !== expectedValue) {
      failures.push(
        `vercel.json ${field} must be ${JSON.stringify(expectedValue)}.`,
      );
    }
  }

  for (const forbiddenField of [
    "build",
    "env",
    "functions",
    "redirects",
    "rewrites",
  ]) {
    if (Object.hasOwn(config, forbiddenField)) {
      failures.push(
        `vercel.json must not define ${forbiddenField} for the static showcase.`,
      );
    }
  }

  if (
    !Array.isArray(config.headers) ||
    config.headers.length !== 1 ||
    config.headers[0]?.source !== "/(.*)"
  ) {
    failures.push(
      "vercel.json must define exactly one all-routes security-header policy.",
    );
    return { headers: [], status: "invalid" };
  }

  const rawHeaders = config.headers[0].headers;
  if (!Array.isArray(rawHeaders)) {
    failures.push(
      "vercel.json all-routes policy must contain a headers array.",
    );
  }
  const configuredHeaders = Object.fromEntries(
    (Array.isArray(rawHeaders) ? rawHeaders : []).map((header) => [
      header?.key,
      header?.value,
    ]),
  );
  for (const [key, expectedValue] of Object.entries(REQUIRED_VERCEL_HEADERS)) {
    if (configuredHeaders[key] !== expectedValue) {
      failures.push(
        `vercel.json header ${key} is missing or differs from the approved static policy.`,
      );
    }
  }

  const unexpectedHeaders = Object.keys(configuredHeaders).filter(
    (key) => !Object.hasOwn(REQUIRED_VERCEL_HEADERS, key),
  );
  if (unexpectedHeaders.length > 0) {
    failures.push(
      `vercel.json contains unreviewed headers: ${unexpectedHeaders.join(", ")}`,
    );
  }

  return {
    headers: Object.keys(configuredHeaders).sort(),
    status: "checked",
  };
}

async function verifyPublicShowcase() {
  const files = await walkFiles(outputRoot);
  if (files.length === 0) {
    throw new Error("The public showcase export is empty.");
  }

  const filesByPath = new Map(files.map((file) => [file.path, file]));
  const publicFileAllowlist = await loadPublicFileAllowlist();
  const failures = [];
  const vercelConfiguration = await verifyVercelConfiguration(failures);

  for (const [route, htmlFile] of REQUIRED_HTML_FILES) {
    if (!filesByPath.has(htmlFile)) {
      failures.push(
        `Missing required ${route === "404" ? "404 page" : `route ${route}`}: ${htmlFile}`,
      );
    }
  }

  const emittedHtml = files
    .filter(({ path }) => path.endsWith(".html"))
    .map(({ path }) => path);
  const expectedHtml = new Set(REQUIRED_HTML_FILES.values());
  for (const htmlFile of emittedHtml) {
    if (!expectedHtml.has(htmlFile)) {
      failures.push(`Unexpected HTML route: ${htmlFile}`);
    }
  }

  for (const file of files) {
    const forbiddenPath = findForbiddenPath(file.path);
    if (forbiddenPath) {
      failures.push(`${forbiddenPath.label} is not allowed: ${file.path}`);
      continue;
    }

    try {
      assertAllowedPath(file.path, publicFileAllowlist);
    } catch (error) {
      failures.push(error.message);
    }

    if (file.bytes === 0) {
      failures.push(`Empty files are not allowed: ${file.path}`);
      continue;
    }

    const buffer = await readFile(file.absolutePath);
    const forbiddenBytes = findForbiddenBytes(buffer);
    if (forbiddenBytes) {
      failures.push(`${forbiddenBytes.label} found in ${file.path}`);
    }
  }

  for (const htmlFile of expectedHtml) {
    const outputFile = filesByPath.get(htmlFile);
    if (!outputFile) {
      continue;
    }

    const html = await readFile(outputFile.absolutePath, "utf8");
    if (!html.includes(DISCLOSURE_ATTRIBUTE)) {
      failures.push(
        `Permanent public-demo disclosure is missing from ${htmlFile}`,
      );
    }

    if (!html.includes(DISCLOSURE_TEXT)) {
      failures.push(`Canonical disclosure text is missing from ${htmlFile}`);
    }

    if (/<form\b[^>]*\bmethod=["']?post\b/iu.test(html)) {
      failures.push(`A network-submitting form is not allowed in ${htmlFile}`);
    }
  }

  for (const publicFile of publicFileAllowlist) {
    if (!filesByPath.has(publicFile)) {
      failures.push(`Public asset was not copied to the export: ${publicFile}`);
    }
  }

  if (
    !files.some(
      ({ path }) => path.startsWith("_next/static/") && path.endsWith(".js"),
    )
  ) {
    failures.push(
      "No client JavaScript bundle was emitted under _next/static/.",
    );
  }

  if (
    !files.some(
      ({ path }) => path.startsWith("_next/static/") && path.endsWith(".css"),
    )
  ) {
    failures.push("No stylesheet was emitted under _next/static/.");
  }

  const totalBytes = files.reduce((sum, file) => sum + file.bytes, 0);
  const report = {
    status: failures.length === 0 ? "passed" : "failed",
    artifact: "apps/showcase/out",
    routeManifest: PUBLIC_ROUTE_PATHS,
    required404: "404.html",
    disclosureAttribute: DISCLOSURE_ATTRIBUTE,
    disclosureText: DISCLOSURE_TEXT,
    vercelConfiguration,
    files: files.length,
    totalBytes,
    bytesByExtension: summarizeByExtension(files),
    largestFiles: [...files]
      .sort((left, right) => right.bytes - left.bytes)
      .slice(0, 12)
      .map(({ path, bytes }) => ({ path, bytes })),
    failures,
  };

  console.log(JSON.stringify(report, null, 2));

  if (failures.length > 0) {
    process.exitCode = 1;
  }
}

verifyPublicShowcase().catch((error) => {
  console.error(`Public showcase verification could not run: ${error.message}`);
  process.exitCode = 1;
});
