# Whale Movement — Context & Reference

> **File:** `frontend/src/components/animations/OceanScene.tsx`
> **Last updated:** 2026-03-09
> **Purpose:** Running record of the whale movement system — how it works, why decisions were
> made, what has been tried, and what to do next. Update this file whenever a meaningful
> change is made to the animation.

---

## 1. Coordinate Space & Scene Geometry

| Constant | Value | Meaning |
|---|---|---|
| `SURFACE_Y` | `12` | Y-coordinate of the water surface plane (world units) |
| Camera position | `[sin*6, 6±1.5, 55±4]` | Drifts slowly via `CameraRig` |
| Camera lookAt | `(0, 6, -5)` | `SURFACE_Y − 2` — waterline sits in the middle-lower third of frame |
| Camera FOV | `55°` | At z=0 the visible horizontal extent is roughly ±62 units |
| Fog | `FogExp2(0x031525, 0.008)` | Exponential, very gradual — whales visible to ≈ z=-50 |

**Y-axis orientation:** positive Y is up. The surface is at Y=8; whales swim at Y≈−2 to −4;
the seafloor/background is around Y=−30.

---

## 2. Whale Configurations (5 instances)

All whales are `SwimmingWhale` components driven by a shared `WhaleInstance` config.

| ID | Model | Start position | baseY (≈) | xRange | zRange | bobAmp | swimSpeed | Initial behaviour |
|---|---|---|---|---|---|---|---|---|
| Blue A | blue_whale.glb | `[-30, -5, -30]` | -5 | 7 | 12 | 2.0 | 0.35 | loop swim |
| Blue B | blue_whale.glb | `[30, -5, 8]` | -5 | 7 | 18 | 2.0 | 0.3 | loop swim |
| Humpback A | humpback_whale.glb | `[-14, -4, -8]` | -4 | 8 | 18 | 2.0 | 0.55 | swim1 |
| Humpback B | humpback_whale.glb | `[2, -4, -12]` | -4 | 7 | 14 | 1.8 | 0.45 | **leap1** (guaranteed) |
| Humpback C | humpback_whale.glb | `[18, -4, -5]` | -4 | 8 | 22 | 2.5 | 0.6 | swim3 |

**Scale correction:** each model has a different export scale.
`blue_whale.glb` needs `× 0.014`, `humpback_whale.glb` needs `× 1.05`.
`relativeScale` (1.0–1.3) is multiplied by the norm factor to produce the final scale.

**Blue whales** have a single looping animation clip. They never breach.
**Humpbacks** use the full behaviour FSM (see §4) and do breach.

---

## 3. Swimming Path (no-arc state)

Three independent sinusoidal axes, all driven by `swimT = t * swimSpeed + phase`:

```
X = config.position[0] + sin(swimT × 0.12) × config.xRange      // horizontal sweep
Y = config.position[1] + sin(swimT × 0.18 + phase) × config.bobAmp  // vertical bob
Z = config.position[2] + sin(swimT × 0.07 + phase×2) × config.zRange  // depth sweep
```

- `phase` offsets each whale in time so they are never synchronised.
- Y stays below `SURFACE_Y − 4` for all current configs (max Y ≈ −4 + 2.5 = −1.5 ≪ 12).
- Z range is per-whale (12–22 units) — whales sweep dramatically toward/away from camera,
  creating a strong depth cue. Blue B (zRange=18) ranges from z=−10 to z=26 (29–81 units
  from camera); Humpback C (zRange=22) ranges from z=−27 to z=17.
- During a leap arc all three axes are **locked** to `breachX / (arc-driven) / breachZ`.

**Yaw:** `targetYaw = config.yRot + atan2(dx, 2)` where `dx` is the X velocity.
Lerp factor `0.015` gives a sluggish, massive-animal feel.

**Roll:** `rotation.z = lerp(z, (targetYaw − config.yRot) × 0.12, 0.015)` — banks
slightly into horizontal turns.

**Pitch (swim):** `lerp(x, dy × 0.03, 0.02)` where `dy` is the vertical bob velocity.
Very subtle nose-up/down following the bob.

---

## 4. Humpback Behaviour FSM

Multi-animation state machine. Each state is an entry in `HUMPBACK_BEHAVIOURS`.

```
State = {
  loop:        LoopRepeat | LoopOnce
  repetitions: number
  fadeIn:      cross-fade duration (seconds)
  next:        [clipName, weight][]   ← weighted random pick on finish
}
```

### Available clips
`swim1`, `swim2`, `swim3`, `swim_start`, `swim_end`, `idle1`,
`leap1`, `leap2`, `leap3`,
`swallow1`, `swallow2`,
`turn_L_start/swim1/swim2/end`, `turn_R_start/swim1/swim2/end`

### Transition weights (representative paths)
```
swim1 → swim2(2), swim3(2), idle1(1), leap1(3), swallow1(3), turn_L(2), turn_R(2)
idle1 → swim1(2), swim2(2), leap1(3), leap2(2), swallow1(3), swallow2(2)
leap1 → swim1(3), swim2(2), idle1(1), leap2(2), swallow1(2)
```

Leap clips have weight **3** from swim states — approximately 3/17 ≈ 18% chance of leaping
after any swim cycle. The turn sequences are multi-step chains ending back in swim/leap states.

**Leap detection:** `transitionTo()` checks `clipName.includes("leap")`. When true it
immediately creates a `LeapArc` (see §5). Any non-leap clip clears `leapArcRef`.

---

## 5. Leap Arc System

### Interface
```ts
interface LeapArc {
  startTime:    number;    // performance.now() * 0.001 at clip transition
  duration:     number;    // min(clip.duration, 3.0) — capped at 3 s
  baseY:        number;    // groupRef.position.y at moment of leap (live, not config)
  peakY:        number;    // SURFACE_Y + 14 + rand*4  →  22–26
  breachX:      number;    // frozen X at leap start
  breachZ:      number;    // frozen Z at leap start
  splashedUp:   boolean;
  splashedDown: boolean;
}
```

### Phase calculation
```
elapsed = now − arc.startTime
phase   = clamp(elapsed / arc.duration, 0, 1)
```
`phase` runs 0 → 1 over `duration` seconds (≤ 3 s).

### Arc easing (current — as of 2026-03-08 rev 3)

```
Ascent  phase 0.0 → 0.5   (first half)
  u          = phase / 0.5
  arcProgress = u * (2 - u)              ← easeOutQuad     0 → 1

Descent phase 0.5 → 1.0   (second half)
  u          = (phase - 0.5) / 0.5
  arcProgress = Math.sqrt(1 - u)         ← (1-u)^0.5       1 → 0
```

`g.position.y = arc.baseY + (arc.peakY − arc.baseY) × arcProgress`

**Why this shape:**
- `easeOutQuad` ascent: explosive launch, decelerates to peak.
- `sqrt(1-u)` descent: whale barely moves near the apex (slow early descent), then
  accelerates sharply — the fast final plunge lines up with the GLB skeleton going
  horizontal for re-entry. `d/du = -0.5/sqrt(1-u)`: slow at peak, fast at entry (easeIn).

**Full iteration history on descent easing:**

| Formula | Phase at SURFACE_Y | Verdict |
|---|---|---|
| `(1-u)²` | ≈69% | ❌ Too early — splash before whale cleared the surface |
| `1 - u²` | ≈89% | ❌ Too late — skeleton already back underwater |
| `(1-u)^1.2` | ≈77% (SURFACE_Y=8) → 72% after raise to 12 | ❌ Still too early |
| `sqrt(1-u)` | ≈87.5% | ✅ Matches GLB horizontal re-entry pose |

### Height maths (representative case)
```
baseY  ≈ -4    (swimming depth)
peakY  ≈ 28    (SURFACE_Y=12 + 16, midpoint of 14–18 rand range)
travel  = 32 units

SURFACE_Y crossing on ascent:
  arcProgress = (12 - (-4)) / (28 - (-4)) = 16/32 = 0.50
  easeOutQuad inverse: u*(2-u) = 0.50 → u ≈ 0.293 → phase ≈ 0.146
  → whale breaks surface at ~15% into arc = ~0.44 s into a 3 s breach

SURFACE_Y crossing on descent (sqrt(1-u)):
  sqrt(1-u) = 0.50 → 1-u = 0.25 → u = 0.75
  phase = 0.5 + 0.75 × 0.5 = 0.875
  → whale re-enters at ~87.5% into arc = ~2.63 s into a 3 s breach
  → 73% of total arc time spent above the waterline
  → skeleton mid-arc positions (above surface):
      phase=0.50 (u=0):   arcProgress=1.000, Y=28.0 (peak)
      phase=0.625 (u=0.25): arcProgress=0.866, Y=23.7 (+11.7 above surface)
      phase=0.75 (u=0.50): arcProgress=0.707, Y=18.6 (+6.6 above surface)
      phase=0.875 (u=0.75): arcProgress=0.500, Y=12.0 (SURFACE_Y = entry splash)
      phase=1.0 (u=1.0):   arcProgress=0.000, Y=-4.0 (baseY)
```

### Splash triggers
```ts
// Exit splash — fires when origin breaks SURFACE_Y going up.
// At this point the lower body has cleared the waterline, back/dorsal just clearing.
if (!arc.splashedUp && g.position.y >= SURFACE_Y)  → triggerSplash + splashedUp = true

// Entry splash — fires when origin descends to SURFACE_Y - 5 (ENTRY_Y = 7).
// The humpback back/dorsal is ~5 units above the group origin, so this is the
// moment the back fully submerges — matching the GLB skeleton's horizontal
// re-entry pose.  Particles still spawn at SURFACE_Y=12 (actual waterline), so
// the burst appears right at the water surface above the descending body.
// With sqrt descent: fires at phase ≈ 94%.
const ENTRY_Y = SURFACE_Y - 5;
if (!arc.splashedDown && arc.splashedUp && phase > 0.5 && g.position.y <= ENTRY_Y)
  → triggerSplash + splashedDown = true
```

**Why SURFACE_Y - 5, not SURFACE_Y:**
The group origin is the whale's body centre. The dorsal fin / back is ~5 units above the
origin. Triggering at `SURFACE_Y` means the splash fires when the body centre hits the
waterline — but the skeleton's "fully entered water, going horizontal" pose happens 5 units
later, when the back has fully submerged. The -5 offset aligns the burst with that pose.

**Phase maths (SURFACE_Y=12, ENTRY_Y=7, baseY=-4, peakY=28, sqrt descent):**
```
arcProgress at ENTRY_Y = (7 - (-4)) / (28 - (-4)) = 11/32 = 0.344
sqrt(1-u) = 0.344  →  (0.344)² = 0.118 = 1-u  →  u = 0.882
phase = 0.5 + 0.882 × 0.5 = 0.941   (~94%)
```
Compare to previous (trigger at SURFACE_Y=12): phase ≈87.5% — too early by 7%.

### Pitch during arc
```ts
const vertDir = Math.cos(phase * Math.PI);
// phase=0 → cos=+1 → nose up  (powering out of water)
// phase=0.5 → cos=0 → level   (at peak)
// phase=1.0 → cos=-1 → nose down (re-entry dive)
g.rotation.x = lerp(g.rotation.x, vertDir * 0.28, 0.08);
```

---

## 6. Splash System

Module-level event bus: `_pendingSplashes: Array<{x, z}>`.
`triggerSplash(x, z)` pushes to the queue. `SplashSystem` consumes it each frame.

### Particle pool
| Parameter | Value |
|---|---|
| Pool size | 300 |
| Particles per burst | 55 |
| Lifetime | 2.2 s |
| Gravity | −18 units/s² |
| Horizontal drag | × 0.993 per frame |
| Spawn Y | `SURFACE_Y` (12) |
| Spawn XZ jitter | ±0.75 units |
| upSpeed | `10 + rand × 14` (10–24) |
| horizSpeed | `sqrt(rand) × 8` — sqrt distribution clusters particles centrally |
| Size | `0.12 + rand × 0.28` (0.12–0.40) |
| Size decay | `size × (1 − lifeRatio × 0.6)` |

**Geometry:** `sphereGeometry args=[1, 5, 4]` — low-poly for performance.
**Material:** `MeshBasicMaterial`, additive blending, no fog, no depth write, `frustumCulled=false`.

The sqrt horizontal speed distribution creates a **curtain shape** — most droplets go
nearly straight up near the centre, with sparser spread at the outer edges. This matches
a real breach entry/exit splash better than a uniform disc.

---

## 7. Nose Pitch — Sign Convention

**Positive `rotation.x`** = nose pitches **up** (towards +Y) in Three.js right-hand coords.

| Phase | `cos(phase × π)` | `rotation.x` | Visual |
|---|---|---|---|
| 0 (launch) | +1 | +0.28 rad | Nose up — powering out |
| 0.5 (peak) | 0 | 0 | Level |
| 1.0 (re-entry) | −1 | −0.28 rad | Nose down — diving in |

**Previous bug (fixed 2026-03-08):** A leading minus sign inverted this — whale
had nose-down on launch and nose-up on re-entry.

---

## 8. Camera Rig

```ts
camera.position.x = sin(t × 0.012) × 6          // slow pan ±6 units
camera.position.y = 6 + sin(t × 0.018) × 1.5    // gentle vertical drift
camera.position.z = 55 + sin(t × 0.009) × 4     // slow push/pull
camera.lookAt(0, SURFACE_Y - 2, -5)              // fixed target just below surface
```

The camera never moves more than ±6/±1.5/±4 from `[0, 6, 55]`. The lookAt target
`(0, 6, -5)` keeps the waterline consistently in the lower-middle of the frame.

---

## 9. Other Scene Elements

| Component | Role |
|---|---|
| `InteractiveWaterSurface` | GPU heightfield water at Y=12, vertex wave displacement, animated UV offset, mouse ripple |
| `SurfaceSplash` | 40 ambient droplets bobbing at Y≈8 — background ambience, not breach-linked |
| `Bubbles` | 80 rising bubbles, reset at Y=40 |
| `FloatingParticles` | 200 marine snow particles drifting slowly upward |
| `GodRays` | 24 planes with animated opacity — light shaft effect from above |
| `CausticFloor` | 18 animated ellipses at Y≈−22 — simulated caustic patterns |
| `StarField` | ~1800 procedural stars above the waterline. Placed via golden-angle spiral on a hemisphere (r=200). Each star avoids the GodRays zone (rejects positions where `y > 0.3 * r`). Twinkle animation: `opacity = base + sin(t * twinkleSpeed + phase) * twinkleAmp`, per-star randomised speed (0.3–1.5) and amplitude (0.15–0.4). Additive blending, no depth write. |
| `MilkyWay` | ~5600 galactic particles forming a visible band across the sky. Built from value-noise FBM (`mwFbm`: 4 octaves, persistence 0.45, lacunarity 2.3) for large-scale structure + Gaussian dust distribution (`mwDust`: cross-band sigma=0.28) for concentration. Particles placed in galactic coordinates (longitude + latitude) then rotated to `tilt=0.38 rad, twist=0.5 rad`. Size varies by density (0.08–0.25). Subtle drift animation. |
| `ShootingStars` | 3-slot meteor system. Each slot has independent random spawn timer (4–15 s gap). On spawn: random origin on upper hemisphere, random direction (slightly downward), trail length 6–12 units, speed 15–30 units/s, lifetime 0.4–1.0 s. Rendered as a stretched `PlaneGeometry` oriented along velocity. Opacity fades from 1.0 → 0.0 over lifetime. |
| `WhaleBubbleTrails` | Micro-bubbles streaming from each whale’s body. Pool of 250 tiny spheres (r=0.06–0.15). Each frame, samples 2–3 active whales, spawns 1–2 bubbles at whale position + random offset (±1.5 x, +0.5–1.5 y, ±1.5 z). Bubbles rise at 1.5–3.0 units/s with slight horizontal drift (sin wave, amp 0.3). Lifetime 2–4 s, fade out over last 30%. Additive blending. |
| `Kickstart` | Calls `invalidate()` every frame to prevent browser throttling |

---

## 10. History of Significant Changes

| Date | Change | Reason |
|---|---|---|
| Early session | Added `LeapArc` system | GLB leap animations don't move the group Y — needed programmatic arc |
| Early session | `SURFACE_Y` lowered from 22 → 8 | Surface was too high, whales were below fog |
| Mid session | `baseY` changed from `config.position[1]` → `groupRef.current.position.y` | Snap/jerk at leap start due to bob offset |
| Mid session | Leap `fadeIn` reduced to 0.1 s | Skeleton snaps immediately to breach pose — more dramatic |
| Mid session | `peakY = SURFACE_Y + 14–18` (was lower) | Full whale body needed to clear the surface |
| Mid session | Removed ring ripple system | Looked bad — flat rings looked artificial |
| Mid session | Spread whale X positions to 5 distinct bands | Whales were clustering in centre of frame |
| Mid session | Raised swim `position[1]` to −2 for humpbacks | They were invisible below fog threshold |
| 2026-03-08 | Fixed descent easing: `(1-u)²` → `1 - u²` | `(1-u)²` is easeOut on position (backwards gravity) — whale fell fast from peak, slowed near entry |
| 2026-03-08 | Descent easing `(1-u)^1.2` → `sqrt(1-u)` | Raising SURFACE_Y to 12 pushed the crossing arcProgress to 0.50 which `(1-u)^1.2` reaches at phase≈72% — still too early. `sqrt(1-u)` crosses at phase≈87.5%, matching GLB horizontal pose |
| 2026-03-08 | Entry splash trigger: `<= SURFACE_Y` → `<= SURFACE_Y - 5` | Body centre at SURFACE_Y means back/dorsal is still 5 units above waterline — skeleton not yet horizontal. Lowering threshold by body-half-height moves trigger to phase≈94%, when back has fully submerged |
| 2026-03-08 | Raised `SURFACE_Y` 8 → 12 | Gives whales more vertical room below surface; waterline sits higher in frame |
| 2026-03-08 | Added `zRange` per whale (12–22) | Previous fixed ±5 Z drift was invisible; per-whale ranges create strong toward/away-from-camera depth cue |
| 2026-03-08 | Increased `bobAmp` 0.8–1.0 → 1.8–2.5 | Vertical bob was barely visible; larger values make the swimming motion read clearly |
| 2026-03-08 | Deepened swim `position[1]` to −4/−5 | Extra room from higher SURFACE_Y used to drop whales deeper, reinforcing the underwater perspective |
| 2026-03-08 | Fixed pitch sign: `−vertDir` → `+vertDir` | Nose was down on launch, up on entry — physically reversed |
| 2026-03-09 | Added `StarField` component (~1800 stars) | Night sky above waterline was empty — procedural stars with twinkle fill the dome |
| 2026-03-09 | Added `MilkyWay` galactic band (~5600 particles) | StarField alone looked sparse — value-noise FBM + Gaussian dust creates a visible galactic band |
| 2026-03-09 | Added `ShootingStars` (3-slot meteor system) | Adds rare, dramatic movement to the otherwise static sky |
| 2026-03-09 | Added `WhaleBubbleTrails` | Whales swimming without bubbles looked lifeless — micro-bubble streams add biological realism |
| 2026-03-09 | Replaced `WaterSurface` with `InteractiveWaterSurface` | GPU heightfield with mouse-driven ripples replaces static plane — much more dynamic surface |
| 2026-03-09 | Updated `GodRays` count 14 → 24, `Bubbles` 160 → 80, `FloatingParticles` 300 → 200 | Tuned particle counts for visual balance — more god rays for atmosphere, fewer bubbles/particles to reduce clutter |

---

## 11. Tuning Levers

### Make breaches more frequent
Increase `leap` weight in `HUMPBACK_BEHAVIOURS` `swim*` next arrays (currently 3, max
effective ~5 before it dominates). Or add leap as a possible next from `idle1`.

### Make breaches less frequent
Reduce leap weights to 1–2, or remove them from idle transitions.

### Change time in air
- **More time in air:** increase `arc.duration` cap (currently `min(clipDuration, 3.0)`).
  Raising to `4.0` adds a full second at the peak.
- **Higher peaks:** increase `SURFACE_Y + 14` constant in `transitionTo`. Current range
  is 22–26 Y; raising to `SURFACE_Y + 18–22` adds dramatic height.
- **Curve shape:** descent uses `sqrt(1-u)` = `(1-u)^0.5`. Raising the exponent toward
  `1.0` (linear) brings the SURFACE_Y crossing earlier (~73%); lowering toward `0.3`
  pushes it even later (~93%). The current 0.5 targets ~87.5%.

### Splash appearance
- **Bigger splash:** increase `SPLASH_PER_BURST` (55 → 80+) or `upSpeed` range.
- **Wider spray:** increase the `sqrt(rand) × 8` multiplier (e.g. `× 12`).
- **Longer hang:** increase `SPLASH_LIFETIME` (2.2 → 3.0).
- **Brighter:** change material color from `0xdff4ff` toward pure white `0xffffff`.

### Swimming feel
- **More whale-like undulation:** increase `bobAmp` (currently 0.8–1.0).
- **Faster turns:** increase the Y-rotation lerp factor from `0.015` → `0.04`.
- **Deeper swim depth:** lower `position[1]` further negative (e.g. −5). Note: too deep
  → whale lost in fog.

---

## 12. Open Issues / Ideas

- [ ] **Pitch magnitude at peak:** at phase=0.5 the nose is already back to level.
  A more dramatic breach would hold nose-up through the first 60% of the arc and only
  tip nose-down in the final 20% (re-entry dive). Consider a non-cosine pitch curve.

- [ ] **Tail fluke visibility:** the body is above water at peak but the tail enters
  water at the same rate as the origin. A separate tail-offset animation or a second
  Y offset (e.g. +3 units behind origin) could make the tail-flick more visible.

- [ ] **Entry splash XZ drift:** current entry splash fires at the frozen `breachX/Z`.
  In reality a diving whale enters slightly forward of the breach exit point — a small
  Z offset (e.g. `breachZ − 2`) on the down-splash would look more natural.

- [ ] **Foam ring on entry:** a short-lived expanding circle mesh at `SURFACE_Y` matching
  the splash position could sell the re-entry. Previous attempt was removed; worth
  retrying with a `ring/torus` geometry at low opacity.

- [ ] **Multiple simultaneous breaches:** currently only `leapArcRef` is a single ref per
  whale. Each `SwimmingWhale` has its own `leapArcRef` so multiple whales *can* breach
  simultaneously — this is fine and already works.

- [ ] **Arc asymmetry (35/65 split):** a 35% ascent / 65% descent phase split (instead
  of 50/50) would make the ascent feel faster and the hang longer. Not yet implemented.

- [ ] **Whale Z drift during approach:** currently Z is frozen for the full arc duration.
  Allowing slow Z drift during the descent (not just position.z lock) would give the whale
  a slight forward glide on the way down, which is realistic.
