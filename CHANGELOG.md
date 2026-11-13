# Changelog

## 0.1.6

- New option **Pickup done at** (*Hämtning klar kl.*): on the pickup day, *Pickup soon* turns off at this time instead of at midnight. Empty by default, which keeps the previous behaviour.
- New attribute `pickup_done_time` on *Pickup soon*.

## 0.1.5

- Same as 0.1.4, without Python cache files that were accidentally included in that release. Update to this one.

## 0.1.4

- Service sensors no longer disappear when NVOA stops listing a service for a while. Infrequent services (glass is emptied quarterly) can drop out between periods; the sensor now stays and shows *unknown* instead of becoming unavailable and orphaned after a restart.
- If NVOA brings the service back under a new ID, the existing sensor takes it over by waste type, keeping entity ID and history.
- New attributes on service sensors: `scheduled` and `service_id`.
- Diagnostics download with NVOA's raw response (address redacted).

## 0.1.3

- Redesigned brand images (`icon`, `logo` and dark variants): a single clean bin glyph with a check mark.

## 0.1.2

- Fixed location of the brand images (now in `custom_components/nvoa/brand/`).

## 0.1.1

- Added brand images (`icon`, `logo` and dark variants) in `custom_components/nvoa/brand/`. Shown in Home Assistant 2026.3 and newer.

## 0.1.0

Initial release.

- Config flow with address search against NVOA's web service
- One date sensor per active waste service, discovered automatically
- "Next pickup" sensor with the list of services collected that day
- "Pickup soon" binary sensor with configurable advance notice (options flow)
- Reconfigure flow to change address
- Refresh every 6 hours, re-evaluated at 00:05
- Swedish and English translations
