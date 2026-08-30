import type { Transition, Variants } from "motion/react";

export const premiumEase = [0.22, 1, 0.36, 1] as const;

export const revealVariants: Variants = {
  hidden: { opacity: 0, y: 22, filter: "blur(10px)" },
  visible: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.72, ease: premiumEase },
  },
};

export const revealFromRightVariants: Variants = {
  hidden: { opacity: 0, x: 28, scale: 0.985, filter: "blur(12px)" },
  visible: {
    opacity: 1,
    x: 0,
    scale: 1,
    filter: "blur(0px)",
    transition: { duration: 0.84, ease: premiumEase },
  },
};

export const cascadeVariants: Variants = {
  hidden: {},
  visible: {
    transition: { delayChildren: 0.08, staggerChildren: 0.09 },
  },
};

export function stateTransition(delay = 0): Transition {
  return { duration: 0.44, delay, ease: premiumEase };
}
