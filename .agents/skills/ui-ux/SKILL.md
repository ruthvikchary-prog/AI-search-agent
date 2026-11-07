---
name: ui-ux
description: >-
  Comprehensive UI/UX design system and frontend interaction standards for the
  Multi-Agent Academic Research Assistant. Use whenever designing, modifying,
  or refining the web interface, CSS styling, components, or user experience.
---

# UI/UX Design System & Standards

This skill governs the aesthetic, layout, typography, and interactive standards for the **Multi-Agent Academic Research Assistant** web platform.

## 1. Aesthetic Identity: Modern AI Dark-Glass

The interface follows a high-tech, modern obsidian aesthetic with glassmorphism, precise 1px borders, and vibrant state indicators:

- **Canvas Background**: `#070b14` / `#090d16` (Deep obsidian slate)
- **Card Surfaces**: `#0f172a` / `#111c33` with `backdrop-filter: blur(12px)`
- **Borders**: `rgba(255, 255, 255, 0.08)` (subtle translucent borders)
- **Active / Accent**: `#6366f1` (Electric Indigo), `#06b6d4` / `#38bdf8` (Cyan)
- **Success / Verified**: `#10b981` / `#34d399` (Emerald)
- **Running / In-Progress**: `#f59e0b` / `#fbbf24` (Amber pulse)
- **Error / Rejected**: `#ef4444` / `#f87171` (Crimson)

## 2. Typography Hierarchy

- **UI Headings & Body**: `IBM Plex Sans` / `Inter`, `-apple-system`, `sans-serif`
- **Code, Metrics, & Timestamps**: `IBM Plex Mono` / `JetBrains Mono`, `monospace`
- **Weight Contrast**:
  - Page Titles: 700 bold, `letter-spacing: -0.02em`
  - Section Headings: 600 semibold
  - Body: 400 regular, `line-height: 1.5`
  - Badges & Chips: 500 medium, uppercase or mono

## 3. Component Guidelines

### Buttons
- **Primary Actions** (`.btn-flat-primary`):
  - Gradient: `linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)`
  - Shadow: `0 4px 14px rgba(99, 102, 241, 0.35)`
  - Hover: `linear-gradient(135deg, #4f46e5 0%, #4338ca 100%)` + elevated glow
- **Success Actions** (`.btn-flat-success`):
  - Gradient: `linear-gradient(135deg, #10b981 0%, #059669 100%)`
  - Shadow: `0 4px 14px rgba(16, 185, 129, 0.3)`
- **Secondary / Ghost**:
  - Background: `rgba(30, 41, 59, 0.6)`
  - Border: `1px solid rgba(255, 255, 255, 0.1)`

### Pipeline Nodes
- Rounded container (`border-radius: 9px` to `12px`).
- Subtle card lift on hover: `transform: translateY(-2px); box-shadow: 0 8px 22px rgba(0, 0, 0, 0.35);`.
- Connecting pipes reflect node status with live color shifts.

### Forms & Input Fields
- Dark input background: `#090d16`.
- Border: `1px solid rgba(255, 255, 255, 0.12)`.
- Focus State: Border `#6366f1` with outer ring `0 0 0 3px rgba(99, 102, 241, 0.2)`.

### Command Menu (⌘K)
- Centered floating modal with backdrop blur (`backdrop-filter: blur(8px)`).
- Instant keyboard navigation with arrow keys and `Enter`.

## 4. Animation & Micro-Interactions

- Standard transition timing: `0.15s ease` to `0.2s cubic-bezier(0.16, 1, 0.3, 1)`.
- Use pulse indicators (`@keyframes pulse`) for running background jobs.
- Avoid sudden layout shifts; prefer skeleton loaders or smooth height transitions.

