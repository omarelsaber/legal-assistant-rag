/**
 * Navbar.tsx — Top navigation bar for the Egyptian Law Assistant.
 *
 * Replaces all Lovable branding with a clean Arabic text logo.
 * Responsive: collapses gracefully on mobile.
 */

import { Scale } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

const NAV_LINKS = [
  { href: "/",        label: "الرئيسية" },
  { href: "/chat",    label: "المحادثة" },
  { href: "/about",   label: "عن المنصة" },
];

export function Navbar() {
  const { pathname } = useLocation();

  return (
    <header
      dir="rtl"
      className="sticky top-0 z-50 w-full border-b border-white/10
                 bg-background/80 backdrop-blur-md supports-[backdrop-filter]:bg-background/60"
    >
      <div className="container mx-auto flex h-16 items-center justify-between px-4">

        {/* ── Logo ─────────────────────────────────────────────────── */}
        <Link
          to="/"
          className="flex items-center gap-2 select-none group"
          aria-label="الرئيسية"
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-lg
                          bg-primary/10 ring-1 ring-primary/20
                          group-hover:bg-primary/20 transition-colors">
            <Scale className="h-5 w-5 text-primary" aria-hidden />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-base font-bold tracking-tight text-foreground">
              المستشار القانوني
            </span>
            <span className="text-[10px] text-muted-foreground font-medium">
              مساعد بالذكاء الاصطناعي
            </span>
          </div>
        </Link>

        {/* ── Navigation links ──────────────────────────────────────── */}
        <nav className="hidden md:flex items-center gap-1" aria-label="التنقل الرئيسي">
          {NAV_LINKS.map(({ href, label }) => (
            <Link
              key={href}
              to={href}
              className={`
                px-4 py-2 rounded-lg text-sm font-medium transition-colors
                ${pathname === href
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-white/5"}
              `}
            >
              {label}
            </Link>
          ))}
        </nav>

        {/* ── Mobile: show icon-only nav ────────────────────────────── */}
        <nav className="flex md:hidden items-center gap-1" aria-label="التنقل">
          {NAV_LINKS.map(({ href, label }) => (
            <Link
              key={href}
              to={href}
              className={`
                px-3 py-2 rounded-lg text-xs font-medium transition-colors
                ${pathname === href
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground"}
              `}
            >
              {label}
            </Link>
          ))}
        </nav>

      </div>
    </header>
  );
}
