import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const schemaUrl = new URL("../openapi.json", import.meta.url);
const outputUrl = new URL("../src/openapi.generated.ts", import.meta.url);
const expected = astToString(await openapiTS(schemaUrl));
const actual = await readFile(fileURLToPath(outputUrl), "utf8").catch(() => "");

if (actual !== expected) {
  process.stderr.write(
    "Generated OpenAPI types are stale. Run `npm run openapi:generate --workspace @localguard/contracts`.\n",
  );
  process.exitCode = 1;
}
