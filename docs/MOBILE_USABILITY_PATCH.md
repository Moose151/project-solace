# Project Solace Beta 0.24.2 Mobile Usability Patch

This patch is intentionally small and does not change the core finance calculation logic.

## Changes

- Date fields now use native browser calendar pickers while still being validated by Solace's existing date parser.
- Money and numeric fields now include mobile keyboard hints so phones should open decimal or numeric keypads instead of the full keyboard.
- The mobile hamburger menu no longer leaves lower links trapped behind the fixed bottom navigation bar.
- The mobile calendar uses an agenda-style layout that is easier to read and tap on small screens.
- Desktop calendar behaviour is preserved.

## Test checklist

After deploying, check:

1. Footer shows Project Solace `0.24.2-beta`.
2. Bills → Add/Edit opens date picker for bill dates.
3. Income Sources → Add/Edit opens date picker for known pay date.
4. Planned Purchases → Add/Edit opens date picker for target date.
5. Money fields open the numeric/decimal keypad on mobile.
6. Mobile hamburger menu can scroll to every link and is not blocked by the bottom nav.
7. Calendar is readable on mobile and still uses the grid on desktop.
8. Existing payday, pay split, bills, and planned purchase pages still load normally.
