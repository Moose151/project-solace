# Project Solace v21 - Income Pay Cycle Cleanup

This patch makes income sources the source of truth for household pay-cycle calculations.

## Changes

- Income source date label changed from "Next pay date" to "Known pay date".
- The saved income date is now explicitly treated as a fortnightly schedule anchor and does not need to be manually updated every payday.
- The Income Sources page now shows both:
  - Known payday
  - Upcoming payday calculated from the schedule
- Pay Cycle, Pay Split, Buckets, Payday Checklist, and Dashboard now calculate the household cycle from active income sources when available.
- Settings first payday remains as a fallback only when no active income sources exist.

## Why

Two household incomes can arrive on different days in the same fortnight. The household pay cycle should follow those income schedules instead of an unrelated global first payday setting.
