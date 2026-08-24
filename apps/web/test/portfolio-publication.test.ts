import {
  access,
  copyFile,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  publishScreenshotGeneration,
  type PortfolioFileOperations,
} from "../e2e/portfolio-publication";
import { PORTFOLIO_SCREENSHOT_FILENAMES } from "../e2e/portfolio-support";

const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const temporaryRoots: string[] = [];

async function temporaryDirectory(): Promise<string> {
  const directory = await mkdtemp(path.join(os.tmpdir(), "localguard-portfolio-publication-"));
  temporaryRoots.push(directory);
  return directory;
}

async function writeGeneration(directory: string, marker: string): Promise<void> {
  await mkdir(directory, { recursive: true });
  await Promise.all(PORTFOLIO_SCREENSHOT_FILENAMES.map((filename) => writeFile(
    path.join(directory, filename),
    Buffer.concat([PNG_SIGNATURE, Buffer.from(`${marker}:${filename}`)]),
  )));
}

async function readGeneration(directory: string): Promise<string[]> {
  return Promise.all(PORTFOLIO_SCREENSHOT_FILENAMES.map(async (filename) => (
    (await readFile(path.join(directory, filename))).subarray(PNG_SIGNATURE.length).toString("utf8")
  )));
}

afterEach(async () => {
  await Promise.all(temporaryRoots.splice(0).map((directory) => (
    rm(directory, { recursive: true, force: true })
  )));
});

describe("portfolio screenshot publication", () => {
  it("swaps one complete generation and removes transaction directories", async () => {
    const parent = await temporaryDirectory();
    const staging = path.join(parent, "staging");
    const destination = path.join(parent, "screenshots");
    await writeGeneration(staging, "new");
    await writeGeneration(destination, "old");

    await publishScreenshotGeneration(
      staging,
      destination,
      PORTFOLIO_SCREENSHOT_FILENAMES,
    );

    expect(await readGeneration(destination)).toEqual(
      PORTFOLIO_SCREENSHOT_FILENAMES.map((filename) => `new:${filename}`),
    );
    expect((await readdir(parent)).filter((name) => name.startsWith(".screenshots."))).toEqual([]);
  });

  it("rolls back to the complete previous generation if directory activation fails", async () => {
    const parent = await temporaryDirectory();
    const staging = path.join(parent, "staging");
    const destination = path.join(parent, "screenshots");
    await writeGeneration(staging, "new");
    await writeGeneration(destination, "old");
    const operations: PortfolioFileOperations = {
      access,
      copyFile,
      mkdir,
      readFile,
      rename: async (source, target) => {
        if (source.toString().includes(".screenshots.incoming-") && target === destination) {
          throw new Error("simulated activation failure");
        }
        await rename(source, target);
      },
      rm,
    };

    await expect(publishScreenshotGeneration(
      staging,
      destination,
      PORTFOLIO_SCREENSHOT_FILENAMES,
      operations,
    )).rejects.toThrow(/simulated activation failure/);

    expect(await readGeneration(destination)).toEqual(
      PORTFOLIO_SCREENSHOT_FILENAMES.map((filename) => `old:${filename}`),
    );
    expect((await readdir(parent)).filter((name) => name.startsWith(".screenshots."))).toEqual([]);
  });

  it("rejects an incomplete generation before touching the existing complete set", async () => {
    const parent = await temporaryDirectory();
    const staging = path.join(parent, "staging");
    const destination = path.join(parent, "screenshots");
    await writeGeneration(staging, "new");
    await rm(path.join(staging, PORTFOLIO_SCREENSHOT_FILENAMES[0]!), { force: true });
    await writeGeneration(destination, "old");

    await expect(publishScreenshotGeneration(
      staging,
      destination,
      PORTFOLIO_SCREENSHOT_FILENAMES,
    )).rejects.toThrow();
    expect(await readGeneration(destination)).toEqual(
      PORTFOLIO_SCREENSHOT_FILENAMES.map((filename) => `old:${filename}`),
    );
  });
});
