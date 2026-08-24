"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { UploadAcceptedSchema } from "@localguard/contracts";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { useNotice } from "@/components/providers/notice-provider";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { apiRequest, errorMessage } from "@/lib/api-client";
import { cn } from "@/lib/cn";
import { formatBytes } from "@/lib/format";

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const allowedExtensions = new Set(["pdf", "docx", "txt"]);

const UploadSchema = z.object({
  file: z
    .custom<File>((value) => typeof File !== "undefined" && value instanceof File, "Choose a document to upload")
    .refine((file) => file.size <= MAX_UPLOAD_BYTES, "The document must be 10 MB or smaller")
    .refine((file) => allowedExtensions.has(file.name.split(".").pop()?.toLowerCase() ?? ""), "Choose a PDF, DOCX, or TXT document"),
});

type UploadValues = z.infer<typeof UploadSchema>;

export function UploadDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const { notify } = useNotice();
  const {
    handleSubmit,
    setValue,
    reset,
    setError,
    control,
    formState: { errors },
  } = useForm<UploadValues>({ resolver: zodResolver(UploadSchema) });
  const selectedFile = useWatch({ control, name: "file" });

  const upload = useMutation({
    mutationFn: async ({ file }: UploadValues) => {
      const body = new FormData();
      body.append("file", file, file.name);
      return apiRequest("/documents", UploadAcceptedSchema, { method: "POST", body });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      notify("Document accepted for local processing.");
      reset();
      onClose();
    },
    onError: (error) => setError("file", { message: errorMessage(error) }),
  });

  function chooseFile(file: File | undefined) {
    if (!file) return;
    setValue("file", file, { shouldValidate: true, shouldDirty: true });
  }

  function handleClose() {
    if (upload.isPending) return;
    reset();
    onClose();
  }

  return (
    <Modal
      description="PDF, DOCX, or TXT · maximum 10 MB · up to 100 PDF pages"
      footer={
        <>
          <Button disabled={upload.isPending} onClick={handleClose} variant="secondary">Cancel</Button>
          <Button form="upload-document-form" isLoading={upload.isPending} type="submit">
            {upload.isPending ? "Uploading…" : "Upload document"}
          </Button>
        </>
      }
      onClose={handleClose}
      open={open}
      title="Upload a document"
    >
      <form id="upload-document-form" noValidate onSubmit={handleSubmit((values) => upload.mutate(values))}>
        <input
          accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
          className="sr-only"
          onChange={(event) => chooseFile(event.target.files?.[0])}
          ref={inputRef}
          type="file"
        />
        <button
          className={cn(
            "prompt-starter flex min-h-56 w-full flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center",
            dragging ? "border-evidence bg-evidence-soft" : "border-border bg-surface-raised hover:border-brand/50",
          )}
          onClick={() => inputRef.current?.click()}
          onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            chooseFile(event.dataTransfer.files[0]);
          }}
          type="button"
        >
          <span className="grid size-12 place-items-center rounded-2xl bg-surface text-brand shadow-sm">
            <UploadCloud aria-hidden className="size-6" />
          </span>
          <span className="mt-4 font-semibold">Drop a document here or browse</span>
          <span className="mt-1 text-sm text-muted-foreground">Client checks are for feedback; the local API validates the actual content.</span>
        </button>

        {selectedFile ? (
          <div className="mt-4 flex items-center gap-3 rounded-lg border border-border bg-surface p-3">
            <FileText aria-hidden className="size-5 shrink-0 text-brand" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{selectedFile.name}</p>
              <p className="text-xs text-muted-foreground">{formatBytes(selectedFile.size)}</p>
            </div>
          </div>
        ) : null}
        {errors.file ? <p className="mt-3 text-sm text-danger" role="alert">{errors.file.message}</p> : null}
      </form>
    </Modal>
  );
}
