"use client";

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { viewportCascadeVariants, viewportRevealVariants } from "@/lib/motion";

const revealViewport = {
  amount: 0.16,
  margin: "0px 0px -7% 0px",
  once: true,
} as const;

type RevealProps = {
  children: ReactNode;
  className?: string;
};

export function ScrollReveal({ children, className }: RevealProps) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      className={className}
      initial={reduceMotion ? false : "hidden"}
      variants={reduceMotion ? undefined : viewportRevealVariants}
      viewport={reduceMotion ? undefined : revealViewport}
      whileInView={reduceMotion ? undefined : "visible"}
    >
      {children}
    </motion.div>
  );
}

export function ScrollRevealGroup({ children, className, label }: RevealProps & { label: string }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.section
      aria-label={label}
      className={className}
      initial={reduceMotion ? false : "hidden"}
      variants={reduceMotion ? undefined : viewportCascadeVariants}
      viewport={reduceMotion ? undefined : revealViewport}
      whileInView={reduceMotion ? undefined : "visible"}
    >
      {children}
    </motion.section>
  );
}

export function ScrollRevealItem({ children, className }: RevealProps) {
  return <motion.div className={className} variants={viewportRevealVariants}>{children}</motion.div>;
}
