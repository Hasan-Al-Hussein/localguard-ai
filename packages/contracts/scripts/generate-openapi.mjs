import { writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const schemaUrl = new URL("../openapi.json", import.meta.url);
const outputUrl = new URL("../src/openapi.generated.ts", import.meta.url);
const nodes = await openapiTS(schemaUrl);
await writeFile(fileURLToPath(outputUrl), astToString(nodes), "utf8");
