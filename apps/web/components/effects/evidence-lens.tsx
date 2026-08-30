"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/cn";

type EvidenceLensVariant = "workspace" | "login";

type EvidenceLensProps = {
  className?: string;
  variant?: EvidenceLensVariant;
};

type Lane = {
  y: number;
  bend: number;
  phase: number;
};

const lanes: readonly Lane[] = [
  { y: 0.19, bend: 0.08, phase: 0.02 },
  { y: 0.42, bend: -0.11, phase: 0.31 },
  { y: 0.68, bend: 0.1, phase: 0.58 },
  { y: 0.84, bend: -0.06, phase: 0.79 },
];

function lanePoint(lane: Lane, progress: number, width: number, height: number) {
  const x = width * (0.04 + progress * 0.92);
  const arc = Math.sin(progress * Math.PI) * lane.bend * height;
  return { x, y: height * lane.y + arc };
}

export function EvidenceLens({ className, variant = "workspace" }: EvidenceLensProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const canvasContext = canvas.getContext("2d", { alpha: true });
    if (!canvasContext) return;
    const target: HTMLCanvasElement = canvas;
    const context: CanvasRenderingContext2D = canvasContext;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let width = 0;
    let height = 0;
    let frame = 0;
    let frameTimer = 0;
    let intersecting = true;
    let documentVisible = document.visibilityState === "visible";
    let startTime = performance.now();
    const frameInterval = 1_000 / (variant === "login" ? 15 : 12);

    function resize() {
      const rect = target.getBoundingClientRect();
      const nextWidth = Math.max(1, Math.round(rect.width));
      const nextHeight = Math.max(1, Math.round(rect.height));
      if (nextWidth === width && nextHeight === height) return;
      width = nextWidth;
      height = nextHeight;
      const ratio = Math.min(window.devicePixelRatio || 1, 1.75);
      target.width = Math.round(width * ratio);
      target.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
    }

    function draw(timestamp: number) {
      resize();
      context.clearRect(0, 0, width, height);

      const isLogin = variant === "login";
      const elapsed = reducedMotion.matches ? 0.32 : (timestamp - startTime) / 18_000;
      const pathColor = isLogin ? "103, 232, 210" : "18, 63, 97";
      const signalColor = isLogin ? "191, 249, 239" : "11, 122, 112";
      const nodeColor = isLogin ? "255, 255, 255" : "255, 255, 255";

      context.save();
      context.lineCap = "round";
      context.lineJoin = "round";

      lanes.forEach((lane, laneIndex) => {
        const start = lanePoint(lane, 0, width, height);
        const end = lanePoint(lane, 1, width, height);
        const controlX = width * (laneIndex % 2 === 0 ? 0.46 : 0.57);
        const controlY = height * lane.y + lane.bend * height * 1.9;

        context.beginPath();
        context.moveTo(start.x, start.y);
        context.quadraticCurveTo(controlX, controlY, end.x, end.y);
        context.strokeStyle = `rgba(${pathColor}, ${isLogin ? 0.23 : 0.12})`;
        context.lineWidth = laneIndex === 1 ? 1.2 : 0.85;
        context.stroke();

        const checkpoints = [0.14, 0.39, 0.64, 0.86] as const;
        checkpoints.forEach((progress, checkpointIndex) => {
          const point = lanePoint(lane, progress, width, height);
          const radius = checkpointIndex === 2 ? 2.6 : 1.8;
          context.beginPath();
          context.arc(point.x, point.y, radius, 0, Math.PI * 2);
          context.fillStyle = `rgba(${nodeColor}, ${isLogin ? 0.58 : 0.72})`;
          context.fill();
          context.strokeStyle = `rgba(${signalColor}, ${isLogin ? 0.48 : 0.25})`;
          context.lineWidth = 1;
          context.stroke();
        });

        const progress = (elapsed + lane.phase) % 1;
        const pulse = lanePoint(lane, progress, width, height);
        const glow = context.createRadialGradient(pulse.x, pulse.y, 0, pulse.x, pulse.y, isLogin ? 18 : 15);
        glow.addColorStop(0, `rgba(${signalColor}, ${isLogin ? 0.9 : 0.62})`);
        glow.addColorStop(0.22, `rgba(${signalColor}, ${isLogin ? 0.35 : 0.2})`);
        glow.addColorStop(1, `rgba(${signalColor}, 0)`);
        context.beginPath();
        context.arc(pulse.x, pulse.y, isLogin ? 18 : 15, 0, Math.PI * 2);
        context.fillStyle = glow;
        context.fill();
        context.beginPath();
        context.arc(pulse.x, pulse.y, 2.2, 0, Math.PI * 2);
        context.fillStyle = `rgba(${signalColor}, 0.92)`;
        context.fill();
      });

      context.restore();
    }

    function animate(timestamp: number) {
      if (intersecting && documentVisible) draw(timestamp);
      if (intersecting && documentVisible && !reducedMotion.matches) {
        frameTimer = window.setTimeout(() => {
          frame = window.requestAnimationFrame(animate);
        }, frameInterval);
      }
    }

    function schedule() {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(frameTimer);
      if (intersecting && documentVisible && !reducedMotion.matches) {
        frame = window.requestAnimationFrame(animate);
      }
    }

    function restart() {
      startTime = performance.now();
      draw(startTime);
      schedule();
    }

    const resizeObserver = new ResizeObserver(() => draw(performance.now()));
    const intersectionObserver = new IntersectionObserver(([entry]) => {
      intersecting = entry?.isIntersecting ?? true;
      if (intersecting) draw(performance.now());
      schedule();
    });
    const handleVisibility = () => {
      documentVisible = document.visibilityState === "visible";
      if (documentVisible) draw(performance.now());
      schedule();
    };

    resizeObserver.observe(target);
    intersectionObserver.observe(target);
    reducedMotion.addEventListener("change", restart);
    document.addEventListener("visibilitychange", handleVisibility);
    restart();

    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(frameTimer);
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      reducedMotion.removeEventListener("change", restart);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [variant]);

  return <canvas aria-hidden className={cn("evidence-lens", className)} ref={canvasRef} />;
}
