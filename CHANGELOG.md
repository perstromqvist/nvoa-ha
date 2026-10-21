# Changelog

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
