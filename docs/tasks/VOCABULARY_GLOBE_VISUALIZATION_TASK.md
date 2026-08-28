# Task: Vocabulary Globe — Illuminate the world with learned words

## Priority

**Priority: immediately after the Profile task.**

Do not start this task before the current Profile task is completed or reaches a stable merged checkpoint.

This task should be treated as the next major user-facing feature after Profile.

---

## Goal

Create an interactive 3D globe that visualizes a user's vocabulary learning progress.

The globe represents the user's vocabulary as many small flame-like light points distributed across the continents:

- each vocabulary item corresponds to one visual flame/point;
- words that have not been learned are dim/gray;
- words that are being learned gradually become brighter;
- mastered words glow using the Flama brand color;
- as the user learns more words, nearby flames collectively illuminate larger portions of the continents;
- a user with a large learned vocabulary should visually appear to have "lit up the world".

The visualization should make learning progress immediately visible without requiring the user to read charts or statistics.

Conceptually:

```text
0 learned
→ dark globe / gray continents

some words learned
→ scattered Flama-colored lights

many words learned
→ dense clusters of light

high mastery
→ continents become strongly illuminated
```

The visual identity should feel like knowledge progressively lighting the world, not like a conventional heatmap dashboard.

---

## Core behavior

### One vocabulary item = one logical point

The source data should represent individual vocabulary items rather than only aggregate deck statistics.

A vocabulary item should have enough visualization state to derive at least:

```text
vocabulary/note id
learning/mastery state
```

The visualization must not require sending the full note content, examples, audio, templates, or complete review history just to draw the globe.

Detailed note data should only be fetched when the user actually interacts with a word if needed.

### Stable placement

A vocabulary item's position should be deterministic.

Reloading the page must not randomly move all vocabulary points to new locations.

Use a stable identifier such as the note/vocabulary ID to deterministically assign the point to a position on land.

The exact geographic location does **not** need to represent the language or origin of the word. The continents are primarily a progress canvas.

### Continent-only placement

Points should appear on land/continent areas rather than being uniformly scattered across oceans.

Investigate a suitable continent/land mask source such as GeoJSON or a preprocessed geographic point set.

The runtime should avoid performing expensive point-in-polygon work for tens of thousands of points on every render. Prefer preprocessing or cached deterministic slots where appropriate.

### Density represents accumulated knowledge

The globe should keep a stable physical size.

As the number of vocabulary items grows, points become visually denser rather than expanding the globe.

Example:

```text
500 words
→ sparse flames

5,000 words
→ recognizable illuminated regions

30,000 words
→ dense illuminated continents
```

Overlapping glow/additive light should naturally make dense learned areas brighter.

---

## Learning state visualization

Do not limit the design to a permanent binary `learned = true/false` model if existing study data can provide a better mastery signal.

Investigate how Flama's current scheduler/study state can produce a normalized mastery value such as:

```text
0.0 = new / not learned
1.0 = strongly mastered
```

The visual mapping can then approximately behave like:

```text
new
→ gray / almost no emission

learning
→ faint Flama glow

reviewing
→ medium brightness

mastered
→ strong Flama glow
```

The exact mastery formula should be derived from the canonical study state rather than duplicating scheduler logic in the frontend.

The visualization must remain understandable even if the detailed state model changes later.

---

## Rendering architecture

This feature is expected to support users with large vocabulary collections, with **30,000 words as a normal realistic dataset** and a design that should not fundamentally break around 100,000 items.

Do not create one React component, DOM element, SVG element, or independent Three.js mesh per vocabulary item.

Investigate a GPU-oriented implementation, preferably around the existing React frontend using technologies such as:

```text
React
↓
React Three Fiber
↓
Three.js / WebGL
↓
BufferGeometry / THREE.Points or GPU instancing
↓
custom shader / efficient flame effect
```

The exact implementation may change after profiling, but the core requirement is that vocabulary points should be rendered in very few draw calls rather than thousands of independent objects.

### Flame appearance

A flame does not need to be a full 3D model.

Prefer lightweight GPU-rendered flame-like points/billboards/particles whose appearance can be produced through shader logic, sprite shaping, noise, flicker, glow, or similar techniques.

Avoid cloning a GLB/mesh object tens of thousands of times unless benchmarking demonstrates that an alternative is clearly superior.

Animation should primarily happen on the GPU. Do not loop over all vocabulary items in JavaScript every animation frame to animate flicker, opacity, or position.

A typical model should be closer to:

```text
CPU updates one `time` uniform
↓
GPU animates all flame points
```

rather than:

```text
30,000 JS objects updated × 60 FPS
```

---

## Performance requirements

Performance on mobile and weaker devices is a first-class requirement, not a later optimization.

### Baseline target

For approximately 30,000 vocabulary items:

- desktop/laptop should aim for smooth 60 FPS interaction;
- normal modern mobile devices should aim for approximately 60 FPS where practical;
- weaker/older phones should remain usable, with a 30 FPS degraded mode acceptable;
- avoid large frame-time spikes while rotating or zooming the globe;
- avoid excessive memory use from one object/component per word.

### Adaptive rendering quality

Provide a strategy for different device capabilities.

For example:

```text
High
- full vocabulary point set
- stronger flame animation
- bloom/glow enabled
- higher render resolution

Medium
- full or nearly full point set
- lower DPR
- cheaper shader
- lower-resolution bloom

Low
- aggregated/LOD point set
- DPR around 1
- simplified glow
- expensive post-processing disabled
```

Exact thresholds should be determined by profiling rather than hard-coded assumptions about device names.

### Device pixel ratio

High-DPR mobile screens can make post-processing disproportionately expensive.

Do not automatically render at the device's maximum DPR.

Investigate a capped/adaptive DPR and adaptive post-processing resolution.

### Bloom and transparency

Glow/bloom is important to the visual concept but must not destroy mobile performance.

Profile:

- transparent particle overdraw;
- additive blending;
- bloom render target resolution;
- framebuffer memory;
- fill rate;
- antialiasing;
- shader complexity.

The visual effect should degrade gracefully before frame rate becomes unusable.

---

## Level of detail / aggregation

At a distant globe view, users cannot visually distinguish tens of thousands of individual flames.

Use level-of-detail or aggregation when it provides a meaningful performance win.

Possible behavior:

```text
far zoom
→ aggregated light cells / reduced visual point set

medium zoom
→ larger point set

close zoom
→ individual vocabulary points and interaction
```

Aggregation must preserve the perceived total learning density/brightness.

A low-end device displaying 10,000 aggregated visual cells may still represent 30,000 logical vocabulary items.

Do not confuse the number of rendered particles with the number of vocabulary records.

---

## Interaction

The first version should prioritize the globe and progress visualization itself.

If individual point interaction is implemented, possible behavior includes:

```text
hover/tap flame
→ resolve point index to vocabulary/note id
→ show lightweight word status

explicit open action
→ fetch full note details if needed
```

Do not load full data for every note simply to support a tooltip.

On mobile, interaction must not depend on hover.

Consider disabling expensive per-point hit-testing while the camera is far away or while the globe is actively moving.

---

## Data/API boundary

Create or reuse a lightweight backend boundary suitable for visualization.

The globe should ideally receive compact data such as:

```json
{
  "revision": 123,
  "items": [
    { "id": "...", "mastery": 0.0 },
    { "id": "...", "mastery": 0.62 },
    { "id": "...", "mastery": 1.0 }
  ]
}
```

This is illustrative, not a required final schema.

Requirements:

- do not expose another user's learning data;
- do not send unnecessary note contents;
- keep payload reasonable for tens of thousands of entries;
- investigate compact representations if JSON becomes materially expensive;
- avoid recomputing expensive globe layout data on every request;
- preserve compatibility with future incremental updates/deltas if the dataset becomes large enough to justify them.

---

## React integration

The globe should integrate cleanly into the existing frontend architecture.

React should manage application state, routing, data fetching, loading/error states, accessibility controls, and interaction boundaries.

Three.js/WebGL should own the high-frequency rendering work.

Avoid putting continuously changing animation state into React state.

The feature must not negatively affect unrelated pages when the globe is not mounted.

Lazy-load large 3D/rendering dependencies if that provides a meaningful bundle-size improvement.

---

## Accessibility and fallback

The globe is a visualization, not the only way to understand progress.

Provide a lightweight accessible textual/statistical fallback such as:

```text
Total vocabulary
Learning
Reviewing
Mastered
Mastery percentage
```

Users on unsupported WebGL environments, reduced-motion configurations, or extremely weak devices should still be able to access meaningful progress information.

Respect `prefers-reduced-motion` where applicable by reducing or disabling continuous flame/globe animation.

---

## Research and implementation approach

Before implementing the full feature:

1. Inspect the existing frontend architecture and study-state source of truth.
2. Determine the canonical vocabulary dataset and mastery representation.
3. Prototype continent placement and deterministic point mapping.
4. Build a rendering benchmark using realistic datasets:
   - 1,000 items;
   - 10,000 items;
   - 30,000 items;
   - 100,000 items if practical.
5. Test on desktop and mobile-class hardware/browser environments.
6. Compare rendering approaches such as `THREE.Points`, instancing, shader billboards, and aggregation where useful.
7. Measure the real cost of bloom, transparency, DPR, and interaction.
8. Choose the simplest architecture that meets the visual and performance requirements.
9. Integrate incrementally rather than building the entire feature in one oversized PR.

Do not prematurely optimize based only on theoretical numbers, but do not accept an architecture that obviously creates one application object per vocabulary item either.

---

## Suggested delivery slices

This is a large feature. Split it into independently reviewable checkpoints.

Possible sequence:

```text
Part 1
Globe rendering prototype + land mask + deterministic point placement

Part 2
Canonical backend progress dataset / mastery mapping

Part 3
GPU vocabulary point rendering at 30k scale

Part 4
Flama flame/glow visual design

Part 5
Adaptive quality, LOD and mobile performance

Part 6
Interaction + accessible fallback

Part 7
Regression tests, profiling and production hardening
```

The exact split may be adjusted after inspecting the current codebase.

Each merged part should leave the repository in a working state.

---

## Acceptance criteria

The task is complete when:

- a signed-in user can open an interactive vocabulary globe based on their own learning data;
- vocabulary points are distributed deterministically over land/continent regions;
- unlearned vocabulary appears dim/gray and learned/mastered vocabulary progressively illuminates using Flama's visual identity;
- increased learned vocabulary produces visibly denser/brighter continents;
- approximately 30,000 vocabulary items can be visualized without creating tens of thousands of React/DOM/independent scene objects;
- the renderer uses an efficient GPU-oriented batching strategy;
- mobile quality degrades adaptively rather than simply becoming unusable;
- high DPR and expensive post-processing are controlled;
- the feature has an accessible non-3D progress fallback;
- the globe does not require transferring the complete contents of every note;
- user data isolation and authorization remain correct;
- the implementation is tested with realistic large datasets;
- the feature is documented well enough for later extension.

---

## Non-goals for the first version

Unless clearly justified during implementation, the first version does not need:

- geographically accurate mapping of a word to its linguistic origin;
- a unique handcrafted 3D flame model for every word;
- social/global comparison between users;
- real-time multiplayer globe updates;
- photorealistic Earth rendering;
- rendering every vocabulary item individually at every camera distance;
- moving scheduler/business logic into the frontend.

Keep the first production version focused on one strong idea:

> **The more vocabulary the user masters, the more of their world lights up.**
