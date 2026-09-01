"use client";

import { ServiceHealthSchema, type Role } from "@localguard/contracts";
import { useQuery } from "@tanstack/react-query";
import {
  BadgeInfo,
  BookOpenText,
  ChartNoAxesCombined,
  ChevronRight,
  ClipboardCheck,
  Files,
  LayoutDashboard,
  ListChecks,
  LockKeyhole,
  LogOut,
  Menu,
  RotateCcw,
  ScrollText,
  X,
} from "lucide-react";
import { Link } from "@/components/ui/app-link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { ProofGateMark } from "@/components/brand/proof-gate-mark";
import { EvidenceLens } from "@/components/effects/evidence-lens";
import { useAuth } from "@/components/providers/auth-provider";
import { apiRequest } from "@/lib/api-client";
import { cn } from "@/lib/cn";
import { isPublicShowcase } from "@/lib/deployment-mode";
import { queryKeys } from "@/lib/query-keys";

type NavigationItem = {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  roles?: readonly Role[];
};

const reviewRoles: readonly Role[] = ["reviewer", "admin"];
const navigation: ReadonlyArray<{ label: string; items: readonly NavigationItem[] }> = [
  {
    label: "Work",
    items: [
      { href: "/overview", label: "Overview", icon: LayoutDashboard },
      { href: "/documents", label: "Documents", icon: Files },
      { href: "/ask", label: "Ask LocalGuard", icon: BookOpenText },
    ],
  },
  {
    label: "Actions",
    items: [
      { href: "/approvals", label: "Approvals", icon: ClipboardCheck, roles: reviewRoles },
      { href: "/tasks", label: "Workflow tasks", icon: ListChecks },
    ],
  },
  {
    label: "Assurance",
    items: [
      { href: "/evaluations", label: "Evaluations", icon: ChartNoAxesCombined, roles: reviewRoles },
      { href: "/audit", label: "Audit log", icon: ScrollText, roles: reviewRoles },
    ],
  },
];

const routeLabels: Record<string, string> = {
  overview: "Overview",
  documents: "Documents",
  ask: "Ask LocalGuard",
  approvals: "Approvals",
  tasks: "Workflow tasks",
  evaluations: "Evaluations",
  audit: "Audit log",
};

function NavigationContent({ onNavigate, role }: { onNavigate?: () => void; role?: Role }) {
  const pathname = usePathname();
  return (
    <>
      <Link className="brand-lockup mx-2 mt-2 flex min-h-16 items-center gap-3 px-3" href="/overview" onClick={onNavigate}>
        <span className="proof-brand-tile grid size-10 place-items-center rounded-xl text-white">
          <ProofGateMark className="size-7" />
        </span>
        <span>
          <span className="block font-heading text-sm font-bold tracking-[-0.035em]">LocalGuard <span className="brand-ai">AI</span></span>
          <span className="brand-tagline block text-xs">Evidence before action</span>
        </span>
      </Link>
      <nav aria-label="Primary" className="flex-1 overflow-y-auto px-3 py-4">
        {navigation.map((section) => {
          const visibleItems = section.items.filter((item) => !item.roles || (role != null && item.roles.includes(role)));
          if (!visibleItems.length) return null;
          return (
            <section className="mb-6" key={section.label}>
              <h2 className="nav-section-label mb-2 px-3 text-[0.66rem] font-bold tracking-[0.16em] uppercase">{section.label}</h2>
              <ul className="space-y-1">
                {visibleItems.map((item) => {
                  const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                  const Icon = item.icon;
                  return (
                    <li key={item.href}>
                      <Link
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "nav-item flex min-h-12 items-center gap-2.5 rounded-xl px-2.5 text-sm font-semibold",
                          active && "nav-item-active",
                        )}
                        href={item.href}
                        onClick={onNavigate}
                      >
                        <span className="nav-icon"><Icon aria-hidden className="size-[1.05rem]" /></span>
                        <span>{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </nav>
      <div className="sidebar-footer border-t p-4">
        <div className="privacy-card flex items-center gap-2.5 rounded-xl px-3 py-3 text-xs font-semibold text-evidence">
          <span className="relative grid size-7 place-items-center rounded-lg bg-white/70"><LockKeyhole aria-hidden className="size-3.5" /><span aria-hidden className="privacy-dot absolute -right-0.5 -bottom-0.5" /></span>
          <span>
            <span className="block">{isPublicShowcase ? "Synthetic showcase" : "Local processing"}</span>
            <span className="mt-0.5 block text-[0.6875rem] font-semibold text-evidence-hover">{isPublicShowcase ? "Resets on refresh" : "Private by design"}</span>
          </span>
        </div>
      </div>
    </>
  );
}

function focusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
  )).filter((element) => element.getClientRects().length > 0);
}

export function ProductShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const desktopNavigationRef = useRef<HTMLElement>(null);
  const mobileDrawerRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const health = useQuery({
    queryKey: queryKeys.health,
    queryFn: () => apiRequest("/health/live", ServiceHealthSchema),
    refetchInterval: 30_000,
    retry: 1,
  });
  const pathParts = pathname.split("/").filter(Boolean);
  const currentLabel = routeLabels[pathParts[0] ?? "overview"] ?? "Details";
  const userInitial = user?.display_name.trim().charAt(0).toUpperCase() || "L";

  useEffect(() => {
    if (!mobileOpen) return;
    restoreFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const desktopNavigation = desktopNavigationRef.current;
    const content = contentRef.current;
    if (desktopNavigation) desktopNavigation.inert = true;
    if (content) content.inert = true;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    return () => {
      if (desktopNavigation) desktopNavigation.inert = false;
      if (content) content.inert = false;
      document.body.style.overflow = "";
      restoreFocusRef.current?.focus();
      restoreFocusRef.current = null;
    };
  }, [mobileOpen]);

  useEffect(() => {
    const media = window.matchMedia("(min-width: 72rem)");
    const handleChange = (event: MediaQueryListEvent) => {
      if (event.matches) setMobileOpen(false);
    };
    media.addEventListener("change", handleChange);
    return () => media.removeEventListener("change", handleChange);
  }, []);

  function handleDrawerKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      setMobileOpen(false);
      return;
    }
    if (event.key !== "Tab" || !mobileDrawerRef.current) return;
    const focusable = focusableElements(mobileDrawerRef.current);
    if (!focusable.length) {
      event.preventDefault();
      return;
    }
    const first = focusable[0];
    const last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  async function handleLogout() {
    await logout();
    if (isPublicShowcase) {
      window.location.replace("/");
      return;
    }
    router.replace("/login");
  }

  return (
    <div className="workspace-shell min-h-dvh min-[72rem]:grid min-[72rem]:grid-cols-[var(--sidebar-width)_minmax(0,1fr)]">
      {pathname === "/overview" || pathname === "/ask" ? <EvidenceLens className="workspace-evidence-lens" /> : null}
      <aside className="workspace-sidebar fixed inset-y-0 left-0 z-30 hidden w-[var(--sidebar-width)] flex-col border-r border-border/80 min-[72rem]:flex" ref={desktopNavigationRef}>
        <NavigationContent role={user?.role} />
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 min-[72rem]:hidden">
          <button aria-label="Close navigation overlay" className="absolute inset-0 cursor-default bg-slate-950/55" onClick={() => setMobileOpen(false)} tabIndex={-1} type="button" />
          <aside
            aria-labelledby="mobile-navigation-title"
            aria-modal="true"
            className="workspace-sidebar relative flex h-full w-[min(19rem,88vw)] flex-col border-r border-border shadow-2xl"
            onKeyDown={handleDrawerKeyDown}
            ref={mobileDrawerRef}
            role="dialog"
          >
            <h2 className="sr-only" id="mobile-navigation-title">Workspace navigation</h2>
            <button
              aria-label="Close navigation"
              className="icon-button absolute top-2 right-2 z-10 grid size-11 place-items-center rounded-xl text-muted-foreground hover:bg-surface-raised hover:text-foreground"
              onClick={() => setMobileOpen(false)}
              ref={closeButtonRef}
              type="button"
            >
              <X aria-hidden className="size-5" />
            </button>
            <NavigationContent onNavigate={() => setMobileOpen(false)} role={user?.role} />
          </aside>
        </div>
      ) : null}

      <div className="workspace-content min-w-0 min-[72rem]:col-start-2" ref={contentRef}>
        <header className="workspace-header sticky top-0 z-20 flex h-[var(--topbar-height)] items-center gap-3 border-b border-border/80 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
          <button aria-expanded={mobileOpen} aria-label="Open navigation" className="icon-button grid size-11 place-items-center rounded-xl text-muted-foreground hover:bg-surface-raised hover:text-foreground min-[72rem]:hidden" onClick={() => setMobileOpen(true)} type="button">
            <Menu aria-hidden className="size-5" />
          </button>
          <nav aria-label="Breadcrumb" className="min-w-0">
            <ol className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <li className="hidden sm:block"><Link className="transition-colors hover:text-brand" href="/overview">Workspace</Link></li>
              <li className="hidden sm:block"><ChevronRight aria-hidden className="size-4" /></li>
              <li aria-current="page" className="truncate font-semibold text-foreground">{currentLabel}</li>
            </ol>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <div
              className={cn(
                "health-pill hidden min-h-9 items-center gap-2 rounded-full border px-3 text-xs font-semibold sm:flex",
                health.isError ? "border-danger/30 bg-danger-soft text-danger" : "border-evidence/30 bg-evidence-soft text-evidence",
              )}
              title={isPublicShowcase ? "Static public portfolio showcase" : health.isError ? "The local API is unavailable" : "The local API is available"}
            >
              <span className={cn("size-1.5 rounded-full", health.isError ? "bg-danger" : "bg-evidence")} />
              {isPublicShowcase ? "Public · Synthetic" : health.isError ? "Local API offline" : "Local · Private"}
            </div>
            <div className="hidden items-center gap-2.5 border-l border-border pl-3 sm:flex">
              <span aria-hidden className="user-avatar grid size-9 place-items-center rounded-full font-heading text-xs font-bold">{userInitial}</span>
              <span><span className="block max-w-32 truncate text-sm font-semibold">{user?.display_name}</span><span className="block text-xs capitalize text-muted-foreground">{isPublicShowcase ? "Simulated reviewer" : user?.role}</span></span>
            </div>
            <button aria-label={isPublicShowcase ? "Reset demo" : "Sign out"} className="icon-button grid size-11 place-items-center rounded-xl text-muted-foreground hover:bg-danger-soft hover:text-danger" onClick={handleLogout} title={isPublicShowcase ? "Reset demo" : "Sign out"} type="button">
              {isPublicShowcase ? <RotateCcw aria-hidden className="size-[1.1rem]" /> : <LogOut aria-hidden className="size-[1.1rem]" />}
            </button>
          </div>
        </header>
        {isPublicShowcase ? (
          <aside
            className="sticky z-[19] flex min-h-11 items-center justify-center gap-2 border-b border-evidence/20 bg-[linear-gradient(90deg,rgba(13,148,136,0.11),rgba(255,255,255,0.94),rgba(18,63,97,0.10))] px-4 py-2 text-center text-[0.72rem] leading-4 font-semibold text-foreground backdrop-blur-xl sm:text-xs"
            data-public-demo-disclosure
            data-public-showcase-disclosure
            role="note"
            style={{ top: "var(--topbar-height)" }}
          >
            <BadgeInfo aria-hidden className="size-3.5 shrink-0 text-evidence" />
            <span>Public portfolio demo with synthetic data. No uploads, persistence, live AI, or real-world actions.</span>
          </aside>
        ) : null}
        <main className="workspace-main mx-auto w-full max-w-[var(--content-max)] px-4 py-5 sm:px-6 sm:py-6 lg:px-8" id="main-content" tabIndex={-1}>
          <div className="page-stage" key={pathname}>{children}</div>
        </main>
      </div>
    </div>
  );
}
