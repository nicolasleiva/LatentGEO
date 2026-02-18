"use client";

export default function LoginButton() {
  return (
    <a
      href="/auth/login"
      className="inline-flex items-center justify-center px-6 py-3 text-base font-semibold text-brand-foreground bg-brand rounded-lg shadow-[0_12px_30px_rgba(16,185,129,0.25)] hover:bg-brand/90 transition-all duration-300"
    >
      Log In
    </a>
  );
}
