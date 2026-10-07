"use client";
import { useEffect, useState } from "react";
import { parseTheme, persistTheme, resolveTheme } from "@/lib/research";

export default function ThemeControl() {
  const [theme, setTheme] = useState<"light" | "dark" | "system">("system");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    try { setTheme(parseTheme(localStorage.getItem("finlens-theme"))); } catch { /* Storage may be blocked. */ }
    setReady(true);
    const sync = (event: StorageEvent) => {
      if (event.key !== "finlens-theme") return;
      setTheme(parseTheme(event.newValue));
    };
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);
  useEffect(() => {
    if (!ready) return;
    const media = matchMedia("(prefers-color-scheme: dark)");
    const apply = () => { document.documentElement.dataset.theme = resolveTheme(theme, media.matches); };
    apply(); media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme, ready]);
  return <label className="theme-control">Theme
    <select aria-label="Theme" value={theme} onChange={(event) => {
      const next = parseTheme(event.target.value); setTheme(next);
      try { persistTheme(next, localStorage); } catch { /* Storage access may itself be blocked. */ }
    }}><option value="light">Light</option><option value="dark">Dark</option><option value="system">System</option></select>
  </label>;
}
