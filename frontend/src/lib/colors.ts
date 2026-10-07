import { useEffect, useState } from "react";
import { useStore } from "./store";

// Recharts needs concrete colours, so read the current theme's CSS variables.
const KEYS = ["--c-ir", "--c-jaccard", "--c-pref", "--c-quality", "--c-penalty", "--muted", "--line", "--ink", "--surface"] as const;
export type Palette = Record<(typeof KEYS)[number], string>;

export function usePalette(): Palette {
  const { theme } = useStore();
  const read = () => {
    const cs = getComputedStyle(document.documentElement);
    return Object.fromEntries(KEYS.map((k) => [k, cs.getPropertyValue(k).trim() || "#888"])) as Palette;
  };
  const [p, setP] = useState<Palette>(read);
  useEffect(() => { setP(read()); }, [theme]);
  return p;
}
