<p align="center">
  <img src="https://img.shields.io/badge/NVOA-Sophämtning-2e7d32?style=for-the-badge&logo=homeassistant&logoColor=white" alt="NVOA Sophämtning">
</p>

<h1 align="center">NVOA Waste Pickup for Home Assistant</h1>

<p align="center">
  Never miss a bin day again. Pickup dates from <strong>Nacka Vatten och Avfall</strong> as sensors, ready for notifications and dashboards.
</p>

<p align="center">
  <a href="https://github.com/hacs/integration">
    <img src="https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge" alt="HACS Custom">
  </a>
  <a href="https://github.com/perstromqvist/nvoa-ha/releases">
    <img src="https://img.shields.io/github/v/release/perstromqvist/nvoa-ha?style=for-the-badge" alt="Latest release">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/perstromqvist/nvoa-ha?style=for-the-badge" alt="License">
  </a>
  <a href="https://www.home-assistant.io/">
    <img src="https://img.shields.io/badge/Home%20Assistant-2024.11%2B-blueviolet?style=for-the-badge&logo=homeassistant&logoColor=white" alt="Home Assistant 2024.11+">
  </a>
  <img src="https://img.shields.io/badge/Coding%20by-Claude-D97757?style=for-the-badge" alt="Coding by Claude">
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=perstromqvist&repository=nvoa-ha&category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open in HACS">
  </a>
</p>

---

A read-only custom Home Assistant integration for household waste collection in **Nacka kommun**. It reads the same public web service as NVOA's own [pickup schedule page](https://futureweb.nvoa.se/EDP/FutureWebBasic/SimpleWastePickup/simplewastepickup), so there is nothing to log in to and no API key to request.

> [!NOTE]
> This is an unofficial, independent project. It is not affiliated with or endorsed by Nacka Vatten och Avfall (NVOA).

## ✨ Features

- **Address search in the setup dialog.** Type part of your street address, pick yourself from the matches. No URLs to edit, no YAML.
- **Automatic service discovery.** One date sensor per active service at your address (Restavfall, Mat/Rest, Plast/Papper, Glas and so on). Nothing is hardcoded to specific fee codes, so it works for any combination of bins.
- **Next pickup sensor.** The earliest upcoming date, with the list of what is collected that day.
- **Notification-ready binary sensor.** "Pickup soon" turns on a configurable number of days before a pickup. Trigger your automations on it instead of writing date maths in templates.
- **Bin details as attributes.** Size, type, number of bins, pickup rhythm and which way the bin handle should face.
- **Always current.** Data is refreshed every 6 hours and re-evaluated just after midnight, so "days until" is right without extra API calls.
- **Swedish and English UI.**

## 🧠 How it works

```
NVOA web service ──► coordinator (every 6 h) ──► sensors ──► your automations
                           ▲
                 re-evaluated at 00:05
```

NVOA only exposes the **next** pickup date per service, not a full calendar. When a pickup date has passed, the integration asks NVOA for the next one shortly after midnight.

## 📋 Requirements

- Home Assistant **2024.11.0** or newer
- [HACS](https://hacs.xyz/) (or manual installation)
- A residential address in Nacka kommun that has a waste service with NVOA

## 📦 Installation

### Via HACS (recommended)

1. Click the **Open in HACS** badge above, or go to **HACS → ⋮ → Custom repositories** and add `https://github.com/perstromqvist/nvoa-ha` with category **Integration**.
2. Download **NVOA Waste Pickup**.
3. Restart Home Assistant.

### Manual

Copy the `custom_components/nvoa` folder to `/config/custom_components/nvoa` and restart Home Assistant.

## ⚙️ Setup

1. Go to **Settings → Devices & services → Add integration** and search for **NVOA**.
2. Enter at least 3 characters of your street address, for example `Storgatan 1`.
3. Select your address from the list. Up to 10 matches are shown, so be specific if yours is missing.
4. Done. A device named after your address is created with all entities.

> [!TIP]
> Moving or want to follow a second address? Use **⋮ → Reconfigure** on the integration to change address, or add the integration again for an additional one.

## 🗑️ Entities

All entities belong to one device per address (`NVOA <street>`). Entity IDs below use the example address `Storgatan 1`.

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.nvoa_storgatan_1_restavfall` | date | Next pickup of that service. One sensor per active service. |
| `sensor.nvoa_storgatan_1_mat_rest` | date | Same, for each additional service (Plast/Papper, Glas OF/FG and so on). |
| `sensor.nvoa_storgatan_1_next_pickup` | date | Earliest upcoming pickup across all services. |
| `binary_sensor.nvoa_storgatan_1_pickup_soon` | on/off | On from *N* days before a pickup until the end of the pickup day. |

### Attributes

**Service sensors**

| Attribute | Example | Description |
|-----------|---------|-------------|
| `days_until` | `3` | Days until the pickup. |
| `frequency` | `Fredag udda vecka` | Pickup rhythm as NVOA describes it. |
| `bin_direction` | `Handtag och hjul ut mot vägen` | How the bin should be placed. |
| `bin_size` | `240 L` | Bin volume. |
| `bin_type` | `Tvåfackskärl` | Container type. |
| `number_of_bins` | `1` | Number of bins. |
| `pickups_per_year` | `26` | Pickups per year. |
| `fee_code` | `NYKÄ1` | NVOA's fee code for the service. |

**Next pickup sensor:** `types` (list of what is collected that day) and `days_until`.

**Pickup soon sensor:** `types`, `next_pickup`, `days_until` and `advance_days`.

## 🔔 Options

Open **Configure** on the integration:

| Option | Default | Description |
|--------|---------|-------------|
| Days of advance notice | `1` | The *Pickup soon* sensor turns on this many days before a pickup (0 to 14). `0` means only on the day itself. |

The sensor changes state at about 00:05, so with `1` it is on for the whole day before the pickup and the pickup day itself.

## 🤖 Examples

### Evening reminder

```yaml
automation:
  - alias: "Bin day reminder"
    triggers:
      - trigger: time
        at: "18:00:00"
    conditions:
      - condition: state
        entity_id: binary_sensor.nvoa_storgatan_1_pickup_soon
        state: "on"
      - condition: template
        value_template: >-
          {{ state_attr('binary_sensor.nvoa_storgatan_1_pickup_soon', 'days_until') == 1 }}
    actions:
      - action: notify.notify
        data:
          title: "Sophämtning imorgon"
          message: >-
            {{ state_attr('binary_sensor.nvoa_storgatan_1_pickup_soon', 'types') | join(', ') }}
```

### Dashboard card

```yaml
type: markdown
title: Sophämtning
content: >-
  **Nästa:** {{ states('sensor.nvoa_storgatan_1_next_pickup') }}
  ({{ state_attr('sensor.nvoa_storgatan_1_next_pickup', 'days_until') }} dagar)

  {{ state_attr('sensor.nvoa_storgatan_1_next_pickup', 'types') | join(' + ') }}
```

Remember to replace the entity IDs with your own. You find them under **Settings → Devices & services → NVOA**.

## 🔧 Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| *No addresses found* in setup | Check the spelling, or search with fewer characters. NVOA lists addresses as `Street 12, Area (id)`. |
| *Cannot reach NVOA* | NVOA's web service is down or your Home Assistant has no internet access. Try again later. |
| *Unexpected response* | NVOA returned an error page, or its firewall rejected the request. Enable debug logging (below) and open an issue. |
| Sensor shows *unknown* | The pickup date has passed and the next one has not been published yet. It recovers on the next refresh. |

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.nvoa: debug
```

## 🙋 Contributing

Issues and pull requests are welcome. If you use a service type that gets a poor name, icon or attributes, open an issue with the `Description` and `WasteType` values from your schedule (leave out the address). Tests run with `pytest` using [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component).

## 📄 License

MIT. See [LICENSE](LICENSE).
