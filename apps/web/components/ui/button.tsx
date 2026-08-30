import type { ButtonHTMLAttributes, ReactNode } from "react";
import { LoaderCircle } from "lucide-react";
import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const variantClasses: Record<ButtonVariant, string> = {
  primary: "button-primary",
  secondary: "button-secondary",
  ghost: "button-ghost",
  danger: "button-danger",
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  isLoading?: boolean;
  icon?: ReactNode;
};

export function Button({
  children,
  className,
  disabled,
  icon,
  isLoading = false,
  type = "button",
  variant = "primary",
  ...props
}: ButtonProps) {
  return (
    <button
      aria-busy={isLoading || undefined}
      className={cn(
        "button-base inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 border px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-45",
        variantClasses[variant],
        className,
      )}
      disabled={disabled || isLoading}
      type={type}
      {...props}
    >
      {isLoading ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}
