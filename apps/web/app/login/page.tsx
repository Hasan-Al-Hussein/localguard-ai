"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { LoginRequestSchema, type LoginRequest } from "@localguard/contracts";
import { Eye, EyeOff, LockKeyhole, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/api-client";

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const { user, login } = useAuth();
  const router = useRouter();
  const {
    register,
    handleSubmit,
    resetField,
    formState: { errors, isSubmitting },
  } = useForm<LoginRequest>({
    resolver: zodResolver(LoginRequestSchema),
    defaultValues: { username: "", password: "" },
  });

  useEffect(() => {
    if (user) router.replace("/overview");
  }, [router, user]);

  async function onSubmit(values: LoginRequest) {
    setSubmitError(null);
    const credentials = { ...values };
    // Clear the credential from the live DOM before awaiting the network so
    // screenshots and accessibility snapshots cannot retain it on failure.
    resetField("password");
    try {
      await login(credentials);
      router.replace("/overview");
    } catch (error) {
      setSubmitError(errorMessage(error));
    }
  }

  return (
    <main className="grid min-h-dvh lg:grid-cols-[minmax(25rem,0.92fr)_minmax(34rem,1.08fr)]" id="main-content">
      <section className="relative hidden overflow-hidden bg-[linear-gradient(145deg,#0d3553,#154f74_62%,#0d6e68)] p-12 text-white lg:flex lg:flex-col lg:justify-between xl:p-16">
        <div className="absolute inset-0 opacity-25 [background-image:linear-gradient(rgba(255,255,255,.1)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.1)_1px,transparent_1px)] [background-size:40px_40px]" />
        <div className="absolute -top-28 -right-24 size-[28rem] rounded-full bg-[#67e8d2]/15 blur-3xl" />
        <div className="absolute -bottom-40 -left-28 size-[34rem] rounded-full border border-white/10 bg-white/5" />
        <div className="relative">
          <span className="grid size-12 place-items-center rounded-2xl bg-white/10 shadow-2xl ring-1 ring-white/20 backdrop-blur">
            <ShieldCheck aria-hidden className="size-6" />
          </span>
          <p className="mt-5 font-heading text-xl font-bold tracking-[-0.03em]">LocalGuard AI</p>
        </div>
        <div className="relative max-w-xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/8 px-3 py-1.5 text-xs font-semibold tracking-wide text-[#bff9ef] uppercase backdrop-blur"><span className="size-1.5 rounded-full bg-[#67e8d2] shadow-[0_0_0_4px_rgb(103_232_210/0.12)]" />Private evidence workspace</span>
          <p className="mt-6 font-heading text-4xl leading-[1.08] font-bold tracking-[-0.045em] xl:text-5xl">Every answer has a source. Every action waits for you.</p>
          <p className="mt-6 max-w-lg text-base leading-7 text-slate-200">Inspect policies, find obligations, and review proposed work without sending documents to an external model service.</p>
          <div className="mt-8 flex items-center gap-3 rounded-r-xl border-l-2 border-[#67e8d2] bg-white/5 px-4 py-3 text-sm text-slate-100 backdrop-blur">
            <LockKeyhole aria-hidden className="size-5 text-[#5eead4]" />
            Documents and model requests stay on this machine.
          </div>
        </div>
        <p className="relative text-xs text-slate-300">Portfolio demonstration · Not legal advice</p>
      </section>

      <section className="relative grid place-items-center overflow-hidden px-5 py-10 sm:px-8">
        <div aria-hidden className="absolute top-[10%] right-[5%] size-72 rounded-full bg-evidence-soft/55 blur-3xl" />
        <div className="panel relative w-full max-w-md p-6 sm:p-8">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="brand-mark grid size-10 place-items-center rounded-xl text-white"><ShieldCheck aria-hidden className="size-5" /></span>
            <span className="font-heading font-bold">LocalGuard AI</span>
          </div>
          <p className="text-xs font-bold tracking-[0.14em] text-evidence uppercase">Private workspace</p>
          <h1 className="mt-3 font-heading text-3xl font-bold tracking-[-0.045em]">Sign in to review evidence</h1>
          <p className="mt-3 text-sm text-muted-foreground">Use a local account configured during bootstrap.</p>

          <form className="mt-8 space-y-5" noValidate onSubmit={handleSubmit(onSubmit)}>
            {submitError ? <div className="rounded-lg border border-danger/25 bg-danger-soft p-3 text-sm text-danger" role="alert">{submitError}</div> : null}
            <div>
              <label className="text-sm font-semibold" htmlFor="username">Username</label>
              <input
                autoComplete="username"
                className="mt-2 min-h-12 w-full rounded-xl border border-border bg-surface px-3.5 text-base shadow-sm placeholder:text-slate-400 focus:border-evidence"
                id="username"
                {...register("username")}
              />
              {errors.username ? <p className="mt-1.5 text-sm text-danger" role="alert">{errors.username.message}</p> : null}
            </div>
            <div>
              <label className="text-sm font-semibold" htmlFor="password">Password</label>
              <div className="relative mt-2">
                <input
                  autoComplete="current-password"
                  className="min-h-12 w-full rounded-xl border border-border bg-surface px-3.5 pr-12 text-base shadow-sm placeholder:text-slate-400 focus:border-evidence"
                  id="password"
                  type={showPassword ? "text" : "password"}
                  {...register("password")}
                />
                <button aria-label={showPassword ? "Hide password" : "Show password"} className="icon-button absolute top-0 right-0 grid size-12 place-items-center rounded-r-xl text-muted-foreground hover:bg-surface-raised hover:text-foreground" onClick={() => setShowPassword((value) => !value)} type="button">
                  {showPassword ? <EyeOff aria-hidden className="size-5" /> : <Eye aria-hidden className="size-5" />}
                </button>
              </div>
              {errors.password ? <p className="mt-1.5 text-sm text-danger" role="alert">{errors.password.message}</p> : null}
            </div>
            <Button className="w-full" isLoading={isSubmitting} type="submit">{isSubmitting ? "Signing in…" : "Sign in"}</Button>
          </form>
          <p className="mt-8 text-center text-xs text-muted-foreground">Session credentials are stored in an HttpOnly cookie. No token is written to browser storage.</p>
        </div>
      </section>
    </main>
  );
}
