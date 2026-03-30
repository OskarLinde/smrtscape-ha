# SMRTScape Home Assistant Integration

Custom Home Assistant integration for Toro SMRTScape lighting scenes.

## Features

- authenticate to the SMRTScape cloud
- discover accounts and locations
- expose scenes as Home Assistant switches
- expose scene status and next-status sensors
- expose gateway online/offline state
- expose scene images as Home Assistant image entities when available

## Notes

- scenes are exposed as `switch` entities
- scene images are exposed as `image` entities when a scene has an uploaded photo
- gateway-offline command failures are surfaced as `Gateway offline`
- sentinel timestamps from the SMRTScape API are suppressed in switch attributes
- image bytes are cached in memory and invalidated when image metadata changes

## Limitations

- reverse-engineered integration
- depends on the current SMRTScape web/API behavior
- scene scheduling is not managed by this integration; use the SMRTScape app / web UI for schedule changes
- scene control depends on the gateway being online
- tested mainly against a single account / single location

## Installation

### HACS

Add `https://github.com/OskarLinde/smrtscape-ha` as a HACS custom repository with category **Integration**, install it from HACS, restart Home Assistant, then add the integration from the UI.

### Manual

Copy `custom_components/smrtscape` into your Home Assistant config directory, restart Home Assistant, then add the integration from the UI.

```bash
cp -R custom_components/smrtscape /path/to/home-assistant-config/custom_components/
```

## Security

This integration stores the configured SMRTScape username/password in Home Assistant config entry storage.

Protect accordingly:
- Home Assistant backups
- HA config directory access
- HA administrator access

## Troubleshooting

Test the SMRTScape app / web UI first.

If scene control does not work there either, this integration cannot fix that. In that case the problem is upstream of Home Assistant.

## Repository

- `custom_components/smrtscape/` — integration code
- `docs/api.md` — API notes
- `docs/notes.md` — implementation notes

<!-- noop commit: bump branch head to clear bad cached HACS ref state -->

## Attribution

Reverse engineered and implemented by OpenClaw (Codex/GPT-5.4).

Note: This code has not been reviewed by human eyes. Treat as experimental.
