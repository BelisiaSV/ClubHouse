// Small, dependency-free hex color helpers — just enough to derive a
// hover/active shade from a club's own primary_color without pulling in a
// color library for one calculation.

function clamp(n) {
  return Math.max(0, Math.min(255, n));
}

export function shadeHex(hex, amount) {
  // amount < 0 darkens, amount > 0 lightens. hex may or may not have a leading '#'.
  const match = /^#?([0-9a-f]{6})$/i.exec(hex || "");
  if (!match) return hex;
  const num = parseInt(match[1], 16);
  const r = clamp(((num >> 16) & 0xff) + amount);
  const g = clamp(((num >> 8) & 0xff) + amount);
  const b = clamp((num & 0xff) + amount);
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, "0")}`;
}

export function isValidHexColor(value) {
  return /^#[0-9a-f]{6}$/i.test(value || "");
}
