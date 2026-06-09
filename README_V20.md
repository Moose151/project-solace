# Project Solace v20 - Bill Entry and Calendar Refinement

This release simplifies recurring bill date entry and improves the monthly calendar.

## Changes

- Replaced the confusing visible Due day / Due month / Start date bill-entry pattern with a single **First due date** field.
- Solace still stores the internal recurrence fields, but users no longer need to understand them.
- Added clearer date help text explaining how weekly, fortnightly, monthly, quarterly, six-monthly, and yearly bills repeat.
- Updated the bills list to show the first due date instead of the internal due-day fields.
- Improved calendar navigation with previous/next/this month controls and month pills.
- Highlighted the current day in the calendar.
- Improved calendar event styling for bills, income, paid items, and skipped items.
- Improved mobile behaviour for the calendar controls.

## Notes

Existing recurring bills continue to work. When editing an existing bill, the new First due date field is populated from the bill's stored start date.
