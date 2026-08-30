"use client";

import Image from "next/image";
import { useRef, useState } from "react";
import { Braces, FileText, Fingerprint, ShieldCheck } from "lucide-react";
import { useInView, useReducedMotion } from "motion/react";
import { cn } from "@/lib/cn";
import evidenceVaultHero from "@/public/brand/evidence-vault-hero.png";

type ProofCoreSceneProps = {
  className?: string;
  compact?: boolean;
  priority?: boolean;
};

const stages = [
  { icon: FileText, label: "Document", className: "proof-node-source" },
  { icon: Braces, label: "Exact anchor", className: "proof-node-anchor" },
  { icon: Fingerprint, label: "Cited answer", className: "proof-node-answer" },
  { icon: ShieldCheck, label: "Human gate", className: "proof-node-gate" },
] as const;

export function ProofCoreScene({ className, compact = false, priority = false }: ProofCoreSceneProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [posterFailed, setPosterFailed] = useState(false);
  const inView = useInView(rootRef, { amount: 0.12, margin: "120px" });
  const reduceMotion = useReducedMotion();
  const animateFlow = inView && !reduceMotion;

  return (
    <div
      aria-label="Evidence flows from a local document through an exact source anchor and cited answer to a human approval gate."
      className={cn("proof-core-scene", compact && "proof-core-scene-compact", className)}
      data-active={animateFlow ? "true" : "false"}
      ref={rootRef}
      role="img"
    >
      {!posterFailed ? (
        <Image
          alt=""
          aria-hidden
          className="proof-core-poster"
          fill
          onError={(event) => {
            console.error("Proof core poster failed to load; using the local CSS evidence scene.", event.currentTarget.currentSrc);
            setPosterFailed(true);
          }}
          preload={priority}
          sizes={compact ? "(max-width: 767px) 100vw, 42vw" : "(max-width: 767px) 100vw, 52vw"}
          src={evidenceVaultHero}
        />
      ) : null}
      <div aria-hidden className="proof-core-depth" />
      <div aria-hidden className="proof-flow-rail" />
      <span aria-hidden className="proof-flow-packet">
        <Braces />
      </span>
      <span aria-hidden className="proof-anchor-reticle">
        <span />
      </span>
      <span aria-hidden className="proof-citation-confirm">
        <Fingerprint />
        <span>Bound</span>
      </span>
      <div aria-hidden className="proof-core-gate">
        <span className="proof-gate-scan" />
      </div>
      <div className="proof-core-nodes">
        {stages.map(({ icon: Icon, label, className: nodeClass }, index) => (
          <span aria-hidden className={cn("proof-node", nodeClass)} key={label}>
            <span className="proof-node-index">0{index + 1}</span>
            <Icon className="size-3.5" />
            <span>{label}</span>
          </span>
        ))}
      </div>
      <div aria-hidden className="proof-core-status">
        <span />Bound source · approval required
      </div>
    </div>
  );
}
