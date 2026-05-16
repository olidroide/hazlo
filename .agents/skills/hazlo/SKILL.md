---
name: hazlo
description: Domain knowledge for the Hazlo event agenda project. Covers the event data model, source administration panel, human review flow, and deployment architecture.
---

## Event Model (required fields)
title, location (address + neighborhood + metro), start_datetime, end_datetime,
price (amount + is_free), ticket_url (required if paid), is_children_activity,
is_toddler_friendly, source_url, extracted_at, status (pending|approved|rejected|published)

## Key Use Cases
- CreateEventFromSource: ingest raw event → normalize → status=pending
- ReviewEvent: approve/reject/edit → status=approved|rejected
- ScheduleSourceFetch: trigger adapter → store extraction run

## Source Admin Panel routes
- GET  /admin/sources              → list with last run status
- POST /admin/sources              → create new source
- GET  /admin/sources/{id}         → detail + parse preview
- GET  /admin/sources/{id}/history → extraction history

## Review Flow routes  
- GET   /admin/events?status=pending  → review queue
- PATCH /admin/events/{id}/review     → approve/reject with HTMX swap