import { useEffect } from "react";
import { shadeHex } from "../utils/color";

/**
 * Applies the logged-in club's own branding colors as CSS custom properties
 * on the document root, so any element can pick them up via var(--club-
 * primary) / the .btn-brand,.text-brand,.ring-brand helpers in index.css —
 * this is what makes "club moet zijn eigen kleuren kunnen aanpassen" apply
 * everywhere at once instead of per-component prop drilling.
 */
export default function useClubTheme(club) {
  useEffect(() => {
    const root = document.documentElement;
    const primary = club?.primary_color || "#059669";
    const secondary = club?.secondary_color || "#111827";
    root.style.setProperty("--club-primary", primary);
    root.style.setProperty("--club-primary-hover", shadeHex(primary, -24));
    root.style.setProperty("--club-secondary", secondary);
  }, [club?.primary_color, club?.secondary_color]);
}
