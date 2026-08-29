/** Unclamped line surface from shared sorted worlds. */
import { fromWorlds } from "./worlds.ts";

export interface LineSurface {
  offered_line: number;
  offered_probability: number;
  break_even_line: number;
  true_unclamped_line_tolerance: number;
  edge_elasticity: number;
  robustness_area: number;
}

export function lineSurface(values: number[], offeredLine: number, playableP = 0.58): LineSurface {
  const xs = [...values].sort((a, b) => a - b);
  const offered = fromWorlds(xs, offeredLine);
  const step = 0.5;
  let tolUp = 0;
  let line = offeredLine;
  while (line < offeredLine + 40) {
    if (fromWorlds(xs, line + step).pHigher < playableP) break;
    line += step;
    tolUp += step;
  }
  let tolDown = 0;
  line = offeredLine;
  while (line > offeredLine - 40) {
    if (fromWorlds(xs, line - step).pLower < playableP) break;
    line -= step;
    tolDown += step;
  }
  let lo = offeredLine - 20;
  let hi = offeredLine + 20;
  let be = offeredLine;
  let best = Math.abs(offered.pHigher - 0.5);
  for (let i = 0; i < 24; i++) {
    const mid = (lo + hi) / 2;
    const p = fromWorlds(xs, mid).pHigher;
    const err = Math.abs(p - 0.5);
    if (err < best) {
      best = err;
      be = mid;
    }
    if (p > 0.5) lo = mid;
    else hi = mid;
  }
  const elasticity = Math.abs(fromWorlds(xs, offeredLine + 0.5).pHigher - offered.pHigher) / 0.5;
  let area = 0;
  for (let i = -12; i <= 12; i++) {
    if (fromWorlds(xs, offeredLine + i * 0.5).pHigher >= playableP) area += 0.5;
  }
  return {
    offered_line: offeredLine,
    offered_probability: offered.pHigher,
    break_even_line: be,
    true_unclamped_line_tolerance: Math.max(tolUp, tolDown),
    edge_elasticity: elasticity,
    robustness_area: area,
  };
}
