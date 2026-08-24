import { randomUUID } from "node:crypto";
import {
  access,
  copyFile,
  mkdir,
  readFile,
  rename,
  rm,
} from "node:fs/promises";
import path from "node:path";

const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

type FileOperations = {
  access: typeof access;
  copyFile: typeof copyFile;
  mkdir: typeof mkdir;
  readFile: typeof readFile;
  rename: typeof rename;
  rm: typeof rm;
};

const defaultFileOperations: FileOperations = {
  access,
  copyFile,
  mkdir,
  readFile,
  rename,
  rm,
};

async function exists(filePath: string, operations: FileOperations): Promise<boolean> {
  try {
    await operations.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function validatePngSet(
  directory: string,
  filenames: readonly string[],
  operations: FileOperations,
): Promise<void> {
  for (const filename of filenames) {
    const bytes = await operations.readFile(path.join(directory, filename));
    if (
      bytes.length <= PNG_SIGNATURE.length
      || !bytes.subarray(0, PNG_SIGNATURE.length).equals(PNG_SIGNATURE)
    ) {
      throw new Error(`Portfolio capture did not produce a valid PNG for ${filename}`);
    }
  }
}

/**
 * Publish one complete screenshot generation without ever replacing files one-by-one.
 *
 * The incoming generation and backup are siblings of the public directory so every
 * commit/rollback operation is a same-volume directory rename on supported filesystems.
 */
export async function publishScreenshotGeneration(
  stagingDirectory: string,
  screenshotRoot: string,
  filenames: readonly string[],
  operations: FileOperations = defaultFileOperations,
): Promise<void> {
  if (new Set(filenames).size !== filenames.length || filenames.length === 0) {
    throw new Error("Portfolio screenshot filenames must form one non-empty unique set");
  }

  await validatePngSet(stagingDirectory, filenames, operations);

  const parentDirectory = path.dirname(screenshotRoot);
  const rootName = path.basename(screenshotRoot);
  const transactionId = randomUUID();
  const incomingDirectory = path.join(parentDirectory, `.${rootName}.incoming-${transactionId}`);
  const backupDirectory = path.join(parentDirectory, `.${rootName}.backup-${transactionId}`);
  let previousGenerationMoved = false;
  let incomingGenerationActivated = false;

  await operations.mkdir(parentDirectory, { recursive: true });
  await operations.mkdir(incomingDirectory, { recursive: false });

  try {
    for (const filename of filenames) {
      await operations.copyFile(
        path.join(stagingDirectory, filename),
        path.join(incomingDirectory, filename),
      );
    }
    await validatePngSet(incomingDirectory, filenames, operations);

    if (await exists(screenshotRoot, operations)) {
      await operations.rename(screenshotRoot, backupDirectory);
      previousGenerationMoved = true;
    }

    try {
      await operations.rename(incomingDirectory, screenshotRoot);
      incomingGenerationActivated = true;
    } catch (publicationError) {
      if (previousGenerationMoved) {
        try {
          await operations.rename(backupDirectory, screenshotRoot);
          previousGenerationMoved = false;
        } catch (rollbackError) {
          throw new AggregateError(
            [publicationError, rollbackError],
            "Portfolio publication failed and the previous screenshot generation could not be restored",
          );
        }
      }
      throw publicationError;
    }

    if (previousGenerationMoved) {
      await operations.rm(backupDirectory, { recursive: true, force: true });
      previousGenerationMoved = false;
    }
  } finally {
    await operations.rm(incomingDirectory, { recursive: true, force: true });
    if (incomingGenerationActivated) {
      await operations.rm(backupDirectory, { recursive: true, force: true });
    } else if (previousGenerationMoved && !(await exists(screenshotRoot, operations))) {
      await operations.rename(backupDirectory, screenshotRoot);
    }
  }
}

export type { FileOperations as PortfolioFileOperations };
