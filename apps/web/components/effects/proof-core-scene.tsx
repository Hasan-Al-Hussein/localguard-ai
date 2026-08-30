"use client";

import dynamic from "next/dynamic";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { Braces, FileText, Fingerprint, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/cn";

const GlobeCollection = dynamic(
  () => import("@designcodeio/threeui/components/GlobeCollection").then((module) => module.GlobeCollection),
  { ssr: false },
);

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
  const [canAnimate, setCanAnimate] = useState(false);
  const [inView, setInView] = useState(false);
  const [documentVisible, setDocumentVisible] = useState(true);
  const [webglFailed, setWebglFailed] = useState(false);

  useEffect(() => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const connection = navigator as Navigator & { connection?: { saveData?: boolean } };
    const probe = document.createElement("canvas");
    const context = probe.getContext("webgl2") ?? probe.getContext("webgl");
    const hasWebgl = Boolean(context);
    context?.getExtension("WEBGL_lose_context")?.loseContext();
    const updateCapability = () => {
      setCanAnimate(hasWebgl && !reducedMotion.matches && !connection.connection?.saveData && window.innerWidth >= 768);
    };
    const handleVisibility = () => setDocumentVisible(document.visibilityState === "visible");
    updateCapability();
    handleVisibility();
    reducedMotion.addEventListener("change", updateCapability);
    window.addEventListener("resize", updateCapability);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      reducedMotion.removeEventListener("change", updateCapability);
      window.removeEventListener("resize", updateCapability);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, []);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const observer = new IntersectionObserver(([entry]) => setInView(entry?.isIntersecting ?? true), {
      rootMargin: "120px",
    });
    observer.observe(root);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const root = rootRef.current;
    if (!root || !canAnimate || !inView) return;
    const onContextLost = (event: Event) => {
      event.preventDefault();
      setWebglFailed(true);
    };
    const attach = () => root.querySelector("canvas")?.addEventListener("webglcontextlost", onContextLost);
    const detach = () => root.querySelector("canvas")?.removeEventListener("webglcontextlost", onContextLost);
    const mutationObserver = new MutationObserver(() => attach());
    mutationObserver.observe(root, { childList: true, subtree: true });
    attach();
    return () => {
      detach();
      mutationObserver.disconnect();
    };
  }, [canAnimate, inView]);

  const showWebgl = canAnimate && inView && documentVisible && !webglFailed;

  return (
    <div
      aria-label="Evidence flows from a local document through an exact source anchor and cited answer to a human approval gate."
      className={cn("proof-core-scene", compact && "proof-core-scene-compact", className)}
      ref={rootRef}
      role="img"
    >
      <Image
        alt=""
        aria-hidden
        className={cn("proof-core-poster", showWebgl && "proof-core-poster-dimmed")}
        fill
        priority={priority}
        sizes={compact ? "(max-width: 767px) 100vw, 42vw" : "(max-width: 767px) 100vw, 52vw"}
        src="/brand/evidence-vault-hero.png"
      />
      {showWebgl ? (
        <div aria-hidden className="proof-core-webgl">
          <GlobeCollection
            brightness={1.08}
            glow={1.2}
            hue={290}
            opacity={0.96}
            saturation={1.28}
            scale={compact ? 0.82 : 0.96}
            smokeScale={1.04}
            smokeSpeed={0.48}
            smokeStrength={0.72}
            speed={0.36}
            starDensity={0.42}
            starSize={0.62}
            starSpeed={0.18}
          />
        </div>
      ) : null}
      <div aria-hidden className="proof-core-depth" />
      <div aria-hidden className="proof-core-filament" />
      <div aria-hidden className="proof-core-gate" />
      <div className="proof-core-nodes">
        {stages.map(({ icon: Icon, label, className: nodeClass }, index) => (
          <span aria-hidden className={cn("proof-node", nodeClass)} key={label}>
            <span className="proof-node-index">0{index + 1}</span>
            <Icon className="size-3.5" />
            <span>{label}</span>
          </span>
        ))}
      </div>
      <div aria-hidden className="proof-core-status"><span />Local inference · human authority</div>
    </div>
  );
}
