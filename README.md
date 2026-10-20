# NVOA Sophämtning (Home Assistant)

HACS integration for waste pickup schedules from **Nacka Vatten och Avfall (NVOA)**.
Data comes from NVOA's public web service behind
[futureweb.nvoa.se](https://futureweb.nvoa.se/EDP/FutureWebBasic/SimpleWastePickup/simplewastepickup).
Unofficial, not affiliated with NVOA.

## Install

1. HACS → Custom repositories → add this repo as *Integration*, or copy
   `custom_components/nvoa` to `/config/custom_components/`.
2. Restart Home Assistant.
3. Settings → Devices & services → Add integration → **NVOA Sophämtning**.
4. Type part of your street address, pick your address from the list.

## Entities (one device per address)

| Entity | Description |
|---|---|
| `sensor.<address>_<waste type>` | One date sensor per active service (e.g. Restavfall, Mat/Rest, Plast/Papper, Glas). Attributes: `days_until`, `frequency`, `bin_direction`, `bin_size`, `bin_type`, `number_of_bins`, `pickups_per_year`, `fee_code`. |
| `sensor.<address>_next_pickup` | Earliest upcoming date. Attributes: `types` (what is collected that day), `days_until`. |
| `binary_sensor.<address>_pickup_soon` | On from N days before a pickup until the end of the pickup day. Attributes: `types`, `next_pickup`, `days_until`. |

Services are discovered from NVOA, so nothing is hardcoded to specific fee codes.
Data is refreshed every 6 hours and re-evaluated shortly after midnight.

## Options

Configure → *Days of advance notice* (default 1 = on from the day before).
To change address: ⋮ menu on the integration → **Reconfigure**.

## Example automation

```yaml
automation:
  - alias: "Sophämtning imorgon"
    trigger:
      - platform: state
        entity_id: binary_sensor.nvoa_storgatan_1_pickup_soon
        to: "on"
    action:
      - service: notify.notify
        data:
          message: >-
            Hämtning snart: {{ state_attr('binary_sensor.nvoa_storgatan_1_pickup_soon', 'types') | join(', ') }}
```
Adjust the entity id to your address.
