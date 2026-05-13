---
$schema: https://github.com/google-labs-code/design.md
meta:
  name: Paper Agent Design System
  description: Design system for Paper Agent — a research-question-driven AI literature workspace
  version: 1.0.0
  updated: "2026-05-13"

color:
  light:
    background:
      page: "#FAF9F5"
      raised: "#FFFFFF"
      sunken: "#F2F0E9"
      subtle: "#F5F3EE"
      surface: "#FAFAF8"
      surface-hover: "#F5F5F3"
      sidebar: "#F5F5F3"
      input: "#FFFFFF"
      overlay: "rgba(0, 0, 0, 0.4)"
    text:
      primary: "#1F1E1B"
      secondary: "#4A4844"
      muted: "#8C8A82"
      on-accent: "#FFFFFF"
    border:
      default: "#E7E4DA"
      subtle: "#F0EDE5"
      strong: "#D0D0CD"
      focus: "#007AFF"
    accent:
      primary: "#C96442"
      soft: "#F5E6DE"
      alpha: "rgba(201, 100, 66, 0.15)"
    semantic:
      danger: "#B7372E"
      danger-tint: "#F0DCD6"
      sage: "#607368"
      sage-tint: "#E8EDE9"
      gold: "#8A6B2C"
      gold-tint: "#F0E7CF"
      brand: "#124C79"
      brand-tint: "#D4E3F0"
      link: "#007AFF"
    shadow:
      sm: "0 1px 2px rgba(0, 0, 0, 0.04)"
      md: "0 2px 8px rgba(0, 0, 0, 0.08)"
      lg: "0 8px 24px rgba(0, 0, 0, 0.12)"
      toast: "0 4px 16px rgba(0, 0, 0, 0.18)"
      card-hover: "0 2px 12px rgba(0, 0, 0, 0.04)"
    grid:
      color: "rgba(0, 0, 0, 0.04)"
      size: "32px"
  dark:
    background:
      page: "#1F1E1B"
      raised: "#2A2825"
      sunken: "#181715"
      subtle: "#242320"
      surface: "#2A2A2A"
      surface-hover: "#3A3A3A"
      sidebar: "#222222"
      input: "#3A3A3A"
      overlay: "rgba(0, 0, 0, 0.62)"
    text:
      primary: "#ECE9DF"
      secondary: "#B8B5AB"
      muted: "#7A786F"
      on-accent: "#FFFFFF"
    border:
      default: "#34322D"
      subtle: "#2E2D28"
      strong: "#555555"
      focus: "#E08A6A"
    accent:
      primary: "#E08A6A"
      soft: "#361F18"
      alpha: "rgba(224, 138, 106, 0.18)"
    semantic:
      danger: "#E05A4F"
      danger-tint: "#4B2825"
      sage: "#9AD0BB"
      sage-tint: "#213C33"
      gold: "#E2C06F"
      gold-tint: "#3F3520"
      brand: "#7FB7E6"
      brand-tint: "#19384F"
      link: "#5CACFF"
    shadow:
      sm: "0 1px 2px rgba(0, 0, 0, 0.2)"
      md: "0 2px 8px rgba(0, 0, 0, 0.3)"
      lg: "0 8px 24px rgba(0, 0, 0, 0.4)"
      toast: "0 4px 16px rgba(0, 0, 0, 0.3)"
    grid:
      color: "rgba(255, 255, 255, 0.03)"
      size: "32px"

typography:
  font-family:
    display: "'Anthropic Serif', 'Source Serif 4', 'Iowan Old Style', Georgia, 'Songti SC', serif"
    body: "'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', system-ui, 'PingFang SC', sans-serif"
    mono: "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, monospace"
  type-scale:
    hero: "32px"
    display: "32px"
    title: "22px"
    lede: "17px"
    body: "15px"
    meta: "13px"
    micro: "12px"
  line-height:
    tight: "1.15"
    body: "1.55"
    relaxed: "1.65"
  font-weight:
    display: "600"
    body: "400"
    bold: "600"
  letter-spacing:
    display: "-0.01em"
    body: "0"
    uppercase: "0.08em"

spacing:
  scale:
    "1": "4px"
    "2": "8px"
    "3": "12px"
    "4": "16px"
    "5": "20px"
    "6": "24px"
    "7": "32px"
    "8": "40px"
    "10": "60px"

elevation:
  card:
    resting: "0 1px 2px rgba(0, 0, 0, 0.04)"
    hover: "0 2px 12px rgba(0, 0, 0, 0.04)"
  modal:
    box-shadow: "0 2px 8px rgba(0, 0, 0, 0.08)"
  drawer:
    box-shadow: "-24px 0 60px rgba(0, 0, 0, 0.12)"
  toast:
    box-shadow: "0 4px 16px rgba(0, 0, 0, 0.18)"

motion:
  duration:
    instant: "120ms"
    fast: "160ms"
    normal: "200ms"
    slow: "350ms"
  easing:
    default: "ease"
    ease-out: "ease-out"
  animation:
    list-enter:
      name: "fadeSlideIn"
      duration: "0.24s"
      easing: "ease-out"
      stagger: "0.03s"
    modal-enter:
      name: "modalIn"
      duration: "0.18s"
      easing: "ease-out"
    button-press:
      transform: "scale(0.97)"
    toast-enter:
      duration: "0.3s"
      easing: "ease"
    shimmer:
      name: "shimmer"
      duration: "1.5s"
      easing: "infinite linear"

radii:
  xs: "4px"
  sm: "6px"
  md: "10px"
  lg: "12px"
  xl: "16px"
  pill: "999px"

breakpoints:
  desktop: "1100px"
  tablet: "900px"
  mobile: "768px"
  small: "480px"

layout:
  sidebar-width: "240px"
  sidebar-collapsed: "48px"
  content-max-width: "640px"
  main-inner-max-width: "960px"
  drawer-width: "420px"
  agent-panel-width: "360px"
  topbar-height: "48px"
  topbar-height-modern: "74px"

icons:
  favicon:
    type: "inline SVG data URI"
    description: "Rounded square with paper icon, orange dot detail"

icon-svg:
  - name: "sidebar-brand"
    description: "Paper icon: open document with folded corner, orange dot on page"
    view-box: "0 0 32 32"
  - name: "mobile-nav-toggle"
    description: "Three horizontal lines (hamburger)"
    view-box: "0 0 18 18"
  - name: "theme-toggle"
    description: "Circle with four rays (sun icon for dark mode toggle)"
    view-box: "0 0 16 16"
---

# Paper Agent Design Language

## Philosophy

Paper Agent is designed for the reading mind. The visual language treats academic
research as a meditative, iterative practice — not a firehose. Every decision
prioritizes legibility, calm, and focus. The interface recedes so the papers can
speak.

The guiding metaphor is a personal research desk: warm, quiet, well-lit, with
papers spread out for thoughtful examination. The warm-off-white background
(`#FAF9F5`) evokes unbleached paper, not sterile white. The breathing grid
background — a subtle dot-grid that slowly pulses — suggests a gently active
space, a mind at work.

## Color System

The palette is deliberately restrained, built on warm neutrals with a single
terracotta accent point. No brand-blue, no corporate gradient.

**Warm neutrals.** Unlike most productivity tools that use cool grays (Slack,
Notion, Linear), Paper Agent's grays are warm — they lean slightly yellow-brown
rather than blue. `#FAF9F5` for page background, `#F2F0E9` for sunken areas,
`#E7E4DA` for lines. The effect is that of an old library, not a spreadsheet.

**Terracotta accent.** `#C96442` (light mode) / `#E08A6A` (dark mode) serves as
the single interactive accent — active tabs, hover states, primary links, nudge
indicators. It is warm but not urgent: a clay pot, not a stop sign. The accent
appears only where the user needs to act, preserving a calm reading
environment.

**Semantic colors are contextual.** Sage (`#607368`) for positive reading
signals (deep read status, liked papers, progress completion). Gold (`#8A6B2C`)
for intermediate states (skim later, pending). Red (`#B7372E`) for errors and
removal. These never compete with the core UI — they sit inside pills, chips,
and small indicators.

**Dark mode is warm, not blue.** Many dark modes invert to an aggressive cool
dark. This one stays warm: `#1F1E1B` page background (a dark clay), `#ECE9DF`
text (warm ivory). The breathing grid becomes a faint white grid. The dark mode
also gains a subtle radial gradient (top-left blue-violet whisper, top-right
warm orange glow), adding depth without noise.

## Typography

The type system establishes a clear hierarchy between serif display text and
sans-serif body text.

**Serif for high-emphasis text.** Page titles, section headings, paper titles,
and the hero greeting use the display stack (Anthropic Serif, Source Serif 4,
Georgia). The serif brings an editorial, scholarly quality — it signals "this is
worth reading carefully." At large sizes (28–32px), the serif's weight and
letter-spacing make the page title feel like a book chapter heading.

**Sans-serif for everything else.** Body copy, navigation, labels, metadata,
and form elements use Inter or system-ui. This follows the well-established
pattern of serif-headings + sans-body that has become the default for
long-form reading interfaces (Medium, Substack, and most digital publishing).

**Small text is deliberate.** Micro (12px) is reserved for labels, timestamps,
and secondary metadata — always in uppercase with generous letter-spacing.
Meta (13px) carries author names and supporting details. This gives the eye a
clear scanning hierarchy.

## Spacing and Layout

Space is the primary visual organizing tool. The 4px base scale (4, 8, 12, 16,
20, 24, 32, 40, 60) creates consistent rhythm across all components.

**Content width is moderated.** Main content areas max out at 640px for
reading-focused pages and 960px for workspace views. This prevents line lengths
from growing too long and respects the reader's comfort zone (~66 characters).

**Borders replace shadows.** Rather than relying on box-shadows for
containment, the design uses 1px borders (`--line: #E7E4DA`). This is
intentional: flat borders are quieter and more "paper-like" than floating
cards. Shadows are reserved for transient surfaces: modals, drawers, toasts.

**Generous vertical rhythm.** Page sections are separated by 24–32px. List
items use 14–16px vertical padding. The result is airy but connected — items
are clearly grouped without feeling cramped.

## Component Architecture

**Cards** (`border-radius: 12px`, `padding: 20px`, `border: 1px solid --line`)
are the primary container. They sit flush against the page background, using
border alone for delineation. The `.card--inset` variant reverses this for
nested content.

**Buttons** are flat and minimal. The primary button is black (`#000000`) in
light mode, white in dark mode — a high-contrast anchor. Secondary buttons
(`.btn-ghost--outline`) use the line color as border. Danger buttons are red.
Size variants (sm, xs) accommodate toolbar contexts. Button press triggers a
`scale(0.97)` micro-interaction.

**Pills and chips** (`border-radius: 999px`) handle all metadata presentation —
status indicators, keywords, score badges, filters. Status pills have dedicated
color treatments (inbox = accent-soft, deep-read = sage-tint, archived =
transparent). Keyword chips use a brand-tint background for core keywords and
sage/accent tints for secondary categories.

**Paper list items** are the core browsing unit. They show title (serif, 16px),
authors, and a summary snippet. Active items gain a 3px brand-colored left
border. Liked/disliked states show a small dot indicator on the right edge.

**The breathing grid** is the signature decorative element. A fixed-position
pseudo-grid of 32px squares, it slowly pulses from 1.5% to 4.5% opacity over
10 seconds. This is the only ambient animation — it creates a sense of
liveness without drawing attention. On dense pages (search, reading), it
dims to 50% opacity. The animation respects `prefers-reduced-motion`.

**Modals and drawers** serve different purposes. Modals (`z-index: 40`) are
center-positioned, scrim-backed dialogs for confirmations and forms. Drawers
(`z-index: 43`) slide in from the right for the AI Agent panel and detail
views. Both use `scale(0.95) + translateY(-8px)` entrance animation.

**Toasts** appear at bottom-right (`z-index: 60`), with variants for success,
error, warning, and info. They use a dark or color-matched background with
`0.3s ease` transition.

## Motion Design

Motion is minimal and purposeful — never decorative.

**List staggering.** Paper list items fade and slide up (8px) sequentially with
3ms stagger delay between items. This creates a gentle cascading reveal when a
page loads. Max stagger covers 15 items.

**Hover micro-interactions.** Button hover uses 160–180ms transitions for
background-color and border-color. The `.rec-card` (recommendation cards) uses
a 300ms cubic-bezier transition with translateY(-4px) on hover, and its action
buttons fade in with a slight upward slide on card hover. These feel premium
without being slow.

**Modal entrance uses 180ms ease-out**, quick enough to feel immediate but
long enough to register. The scale-transform anchors the eye to the center.

**The shimmer skeleton** (`1.5s infinite linear`) provides loading feedback
for dynamic content. The gradient sweeps left to right at 200% width.

## Responsive Strategy

The design collapses in three stages:

1. **Below 1100px:** Side navigation becomes a horizontal strip. Split layouts
   become single-column.
2. **Below 900px:** Detail panels become bottom sheets (`70vh`, rounded top
   corners, transform-based slide-up). A "mobile back" button appears.
3. **Below 768px:** Everything becomes full-width. Touch targets expand to
   44px minimum. The sidebar becomes a hamburger-revealed overlay. Buttons go
   full-width in button groups.

The detail panel bottom sheet pattern is worth noting: on desktops the detail
sits beside the list in a split layout; on mobile it slides up from the bottom
as a fixed overlay with a related scrim — the same content, different container,
no separate mobile template.

## Accessibility

- `-webkit-font-smoothing: antialiased` and `text-rendering: optimizeLegibility`
  for reading clarity
- `prefers-reduced-motion` disables all motion including list stagger, button
  press, and modal entrance
- `:focus-visible` uses a 2px accent-colored outline with 2px offset
- Semantic heading hierarchy (h1-h4 use serif display family)
- `sr-only` utility class for screen-reader-only content
- Dark mode respects `localStorage` preference and toggles via `data-theme`
  attribute

## Design Intent (What the Tokens Don't Say)

**This interface should feel like a desk, not a dashboard.** Dashboards are for
monitoring. This is for reading. The warm colors, serif typography, and quiet
grid background are all calibrated to lower the user's cognitive heart rate.

**The terracotta accent should be rare.** If the accent color appears on
every element, it loses its signal. The accent says "click here" — it is
intentionally scarce. Navigation items, labels, and borders use the neutral
palette. The accent only appears for: the active tab, the hover state of an
interactive element, the primary action button, and status indicators that
need attention.

**Cards should feel like paper on a desk, not floating windows.** That is why
borders are preferred over shadows. A shadow implies elevation; a 1px border
implies resting on a surface. The distinction is subtle but cumulative.

**The app should work without a page refresh.** Every interaction (marking
read/liked, saving to collection, changing tabs) updates optimistically.
Loading spinners are skeletons, not full-page reloads. The app feels local
because it is — state persists in SQLite, and the AI provider is optional.

**The footer quote is intentional.** "The art of doing research is the art of
making hard choices visible" (paraphrasing John Dewey) appears on every page.
It is a gentle reminder of purpose. It also occupies space that would otherwise
be empty, preventing the bottom of the page from feeling premature.

