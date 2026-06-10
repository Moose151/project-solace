# Project Solace Beta 0.24.1 Stability Notes

Project Solace is still in beta. Earlier v-build labels were internal rapid-build labels, not production release versions. The current stability checkpoint is **Beta 0.24.1**.

This build is focused on reliability before stress testing. Avoid new features until the app has been used through at least one full pay cycle.

## Post-update checklist

After deploying Beta 0.24.1, check:

1. Dashboard loads.
2. Footer shows Project Solace `0.24.1-beta`.
3. System Info loads.
4. Health Check loads.
5. Planned Purchases loads.
6. Pay Cycle current and next load.
7. Payday current and next load.
8. Privacy filter still works.
9. Shared planned purchases still show as household targets.
10. Individual planned purchases still show under the assigned person.
11. Backup download works.
12. Restore page rejects an oversized/invalid upload gracefully.

## Stress-test focus

- Use the app for real pay-cycle planning.
- Check that current and next cycle values make sense.
- Mark bills paid/skipped as they occur.
- Confirm individual planned purchases do not inflate household shared set-aside.
- Export a database backup before and after meaningful data entry.
