# Implementation notes

## Current state

A first prototype integration exists under `custom_components/smrtscape/`.

## Immediate TODOs

- validate against a real Home Assistant instance
- improve config flow client-session import/use
- add retry-on-401 reauthentication logic
- handle multiple accounts and multiple locations more cleanly
- add better entity/device metadata
- consider a coordinator entity rebuild strategy if scenes are added/removed
- add diagnostics / debug logging guidance
- decide whether scene entities should be `switch` only, or also expose buttons/services

## Potential future enhancements

- theme support
- separate entities for next scheduled on/off timestamps
- service calls for timed force duration if API supports it
- HACS metadata and release packaging
- tests with mocked API responses
