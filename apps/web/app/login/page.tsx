"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { LoginRequestSchema, type LoginRequest } from "@localguard/contracts";
import { ArrowRight, Eye, EyeOff, LockKeyhole } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { ProofGateMark } from "@/components/brand/proof-gate-mark";
import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/api-client";
import { cascadeVariants, revealFromRightVariants, revealVariants } from "@/lib/motion";

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const { user, login } = useAuth();
  const router = useRouter();
  const reduceMotion = useReducedMotion();
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
    <main className="login-shell grid min-h-dvh lg:grid-cols-[minmax(34rem,1.18fr)_minmax(28rem,0.82fr)]" id="main-content">
      <section className="login-visual relative hidden overflow-hidden text-white lg:flex lg:min-h-dvh lg:flex-col lg:justify-between">
        <Image
          alt=""
          aria-hidden
          className="login-vault-image object-cover object-[58%_50%]"
          fill
          priority
          sizes="58vw"
          src="/brand/evidence-vault-hero.png"
        />
        <div aria-hidden className="login-vault-overlay" />
        <motion.div
          animate="visible"
          className="relative z-10 flex items-center gap-3 px-12 pt-10 xl:px-16 xl:pt-12"
          initial={reduceMotion ? false : "hidden"}
          variants={revealVariants}
        >
          <span className="proof-brand-tile grid size-12 place-items-center rounded-2xl">
            <ProofGateMark className="size-8" />
          </span>
          <span>
            <span className="block font-heading text-lg font-bold tracking-[-0.035em]">LocalGuard <span className="font-medium text-white/55">AI</span></span>
            <span className="mt-0.5 block font-mono text-[0.58rem] tracking-[0.18em] text-[#74ead6] uppercase">Private evidence engine</span>
          </span>
        </motion.div>

        <motion.div
          animate="visible"
          className="relative z-10 max-w-2xl px-12 pb-8 xl:px-16"
          initial={reduceMotion ? false : "hidden"}
          variants={cascadeVariants}
        >
          <motion.span className="login-kicker" variants={revealVariants}><span />Evidence before action</motion.span>
          <motion.p className="login-display mt-5 max-w-[13ch] font-heading text-[clamp(2.75rem,4.3vw,5.35rem)] leading-[0.96] font-bold tracking-[-0.065em]" variants={revealVariants}>
            Proof you can inspect. <span>Actions you control.</span>
          </motion.p>
          <motion.p className="mt-6 max-w-xl text-base leading-7 text-slate-200/88 xl:text-lg xl:leading-8" variants={revealVariants}>LocalGuard turns private policy documents into source-linked answers and reviewable work, without surrendering the final decision to AI.</motion.p>
          <motion.ol aria-label="LocalGuard evidence flow" className="login-pipeline mt-7 grid max-w-xl grid-cols-3 gap-2" variants={revealVariants}>
            {[
              ["01", "Source", "Local document"],
              ["02", "Proof", "Exact citation"],
              ["03", "Gate", "Human approval"],
            ].map(([index, label, detail]) => (
              <li key={label}>
                <span>{index}</span>
                <strong>{label}</strong>
                <small>{detail}</small>
              </li>
            ))}
          </motion.ol>
        </motion.div>
        <motion.div animate="visible" className="relative z-10 flex items-center justify-between border-t border-white/10 px-12 py-5 text-[0.68rem] text-slate-300/80 xl:px-16" initial={reduceMotion ? false : "hidden"} variants={revealVariants}>
          <span>Engineering demonstration · Not legal advice</span>
          <span className="font-mono tracking-[0.12em]">LG / PRIVATE</span>
        </motion.div>
      </section>

      <section className="login-auth-side relative grid place-items-center overflow-hidden px-5 py-10 sm:px-8">
        <div aria-hidden className="login-auth-glow" />
        <motion.div
          animate="visible"
          className="login-panel panel relative w-full max-w-[29rem] p-6 sm:p-9"
          initial={reduceMotion ? false : "hidden"}
          variants={revealFromRightVariants}
        >
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-3">
              <span className="proof-brand-tile grid size-11 place-items-center rounded-xl"><ProofGateMark className="size-7" /></span>
              <span><span className="block font-heading font-bold">LocalGuard AI</span><span className="block text-[0.65rem] font-semibold tracking-[0.13em] text-evidence uppercase">Evidence before action</span></span>
            </div>
            <p className="mt-3 max-w-sm text-sm leading-6 text-muted-foreground">Private document intelligence with source-linked answers and human-approved actions.</p>
          </div>
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-bold tracking-[0.14em] text-evidence uppercase">Private workspace</p>
            <span className="login-local-status"><span />Local only</span>
          </div>
          <h1 className="mt-4 font-heading text-3xl font-bold tracking-[-0.05em]">Enter the evidence room</h1>
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
            <Button aria-label="Sign in" className="w-full" icon={<ArrowRight aria-hidden className="size-4" />} isLoading={isSubmitting} type="submit">{isSubmitting ? "Signing in…" : "Enter LocalGuard"}</Button>
          </form>
          <div className="mt-8 flex items-start gap-2.5 border-t border-border/70 pt-5 text-xs leading-5 text-muted-foreground"><LockKeyhole aria-hidden className="mt-0.5 size-3.5 shrink-0 text-evidence" /><p>Session credentials stay in an HttpOnly cookie. No token is written to browser storage.</p></div>
        </motion.div>
      </section>
    </main>
  );
}
