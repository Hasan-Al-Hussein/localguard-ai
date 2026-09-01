import NextLink from "next/link";
import type { ComponentProps } from "react";
import { isPublicShowcase } from "@/lib/deployment-mode";

type AppLinkProps = ComponentProps<typeof NextLink>;

function toStaticHref(href: string): string {
  if (!href.startsWith("/") || href.startsWith("//")) return href;
  const match = href.match(/^([^?#]*)(.*)$/);
  const pathname = match?.[1] ?? href;
  const suffix = match?.[2] ?? "";
  if (pathname === "/" || pathname.endsWith("/") || /\.[^/]+$/.test(pathname)) return href;
  return `${pathname}/${suffix}`;
}

export function Link(props: AppLinkProps) {
  if (isPublicShowcase) {
    if (typeof props.href !== "string") {
      throw new Error("Public showcase links must use string href values");
    }
    const staticHref = toStaticHref(props.href);
    return <a {...(props as ComponentProps<"a">)} href={staticHref} />;
  }

  return <NextLink {...props} />;
}
