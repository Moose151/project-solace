# Project Solace v24 Stability Notes

v24 is a stabilisation build. It intentionally avoids large new workflows and focuses on visibility, diagnostics, and planned-purchase clarity.

## Added

- Visible app version marker in the footer.
- Manage -> System Info page.
- Health Check now includes database file and version checks.
- Planned Purchases page has clearer shared vs individual sections.
- Planned purchase summary cards for active targets, shared targets, remaining amount, and active item count.

## Post-update checks

After deploying v24, check:

1. Dashboard loads.
2. Footer shows Project Solace v24.0.
3. Manage -> System Info loads.
4. Manage -> Health Check loads.
5. Planned Purchases shows shared and individual sections.
6. Privacy button still blurs/unblurs money.
7. Payday Checklist current and next cycle both load.
8. Pay Split loads.
9. Calendar loads.
10. Backup download works.

## Freeze recommendation

After v24, avoid new features until the app has been used through at least one full pay cycle. Focus only on bug fixes, backup testing, and small wording/layout fixes.
