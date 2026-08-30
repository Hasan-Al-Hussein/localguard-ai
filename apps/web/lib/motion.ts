import type { Transition, Variants } from "motion/react";

export const premiumEase = [0.22, 1, 0.36, 1] as const;

export const revealVariants: Variants = {
  hidden: { opacity: 0, y: 14 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.38, ease: premiumEase },
  },
};

export const revealFromRightVariants: Variants = {
  hidden: { opacity: 0, x: 18, scale: 0.99 },
  visible: {
    opacity: 1,
    x: 0,
    scale: 1,
    transition: { duration: 0.4, ease: premiumEase },
  },
};

export const cascadeVariants: Variants = {
  hidden: {},
  visible: {
    transition: { delayChildren: 0.04, staggerChildren: 0.045 },
  },
};

export function stateTransition(delay = 0): Transition {
  return { duration: 0.24, delay, ease: premiumEase };
}
