# HomeStack UI v1

HomeStack UI is the shared visual direction for Project Solace, Project Meridian, and the future home server dashboard.

The goal is a warm, minimal household interface: clean enough for daily use, soft enough to feel approachable, and structured enough for admin-style pages.

## Design direction

- Warm beige/cream light theme.
- Warm charcoal dark theme.
- Muted blue accent instead of bright Bootstrap blue.
- Soft cards with subtle borders.
- Clean tables and forms.
- Rounded buttons and consistent action spacing.
- Minimal visual noise, but not empty or sterile.

## Core palette

Light theme:

- Background: `#f6f1e8`
- Surface: `#fffaf2`
- Raised surface: `#ffffff`
- Border: `#ded4c5`
- Text: `#252525`
- Muted text: `#6f6a61`
- Primary: `#3f6f8f`
- Success: `#5f8f6b`
- Warning: `#c98a3d`
- Danger: `#b85c50`

Dark theme:

- Background: `#171615`
- Surface: `#22201d`
- Raised surface: `#2b2824`
- Border: `#403a33`
- Text: `#f2eee7`
- Muted text: `#b8afa3`
- Primary: `#83a9bd`

## Reuse plan

For Meridian and the home server dashboard, copy the CSS variables and base component rules from:

```text
app/static/css/site.css
```

The reusable sections are:

- Navigation
- Page structure
- Cards/panels/metrics
- Buttons
- Forms
- Tables
- Badges/pills/status
- Dashboard widgets
- Calendar/checklist patterns
- Light/dark theme variables

Each app can then add a small app-specific CSS section below the shared HomeStack UI rules.
