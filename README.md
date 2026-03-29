# SMRTScape Home Assistant Integration

Reverse-engineered Home Assistant custom integration for Toro SMRTScape cloud lighting scenes.

## Scope

Current focus:
- authenticate to the SMRTScape cloud
- discover accounts and locations
- enumerate lighting scenes
- expose scenes as Home Assistant switches
- expose status/next-status helper sensors
- expose gateway online/offline state

## Project layout

- `custom_components/smrtscape/` — Home Assistant integration code
- `docs/api.md` — reverse-engineered API notes
- `docs/notes.md` — implementation notes / TODOs

## Install into Home Assistant

Copy `custom_components/smrtscape` into your HA config directory's `custom_components/` folder, then restart Home Assistant.

Example:

```bash
cp -R custom_components/smrtscape /path/to/home-assistant-config/custom_components/
```

## Status

Prototype. Good enough for iterative local testing, not yet polished for public release.
