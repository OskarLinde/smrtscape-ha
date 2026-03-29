# SMRTScape Home Assistant custom integration

Early custom integration for Toro SMRTScape cloud scenes.

## Current scope

- Login to SMRTScape cloud
- Discover locations
- Discover scenes per location
- Expose each scene as a switch
- Turn scenes on/off via the cloud API
- Expose scene status text and next status text as sensors
- Expose gateway online/offline as a binary sensor

## Known API notes

Observed endpoints:

- `POST /api/v1/auth/login`
- `GET /api/v1/accounts/{account_id}`
- `GET /api/v1/locations/{location_id}`
- `GET /api/v1/scenes/location/{location_id}`
- `GET /api/v1/scenes/status/location/{location_id}`
- `GET /api/v1/scenes/schedulesummary/location/{location_id}`
- `PUT /api/v1/scenes/{scene_id}/force?action=on|off&duration=0`

Auth appears to use a bearer token returned by login.

## Install

Copy `custom_components/smrtscape` into your Home Assistant config's `custom_components/` directory, then restart HA.

## Notes

This was reverse-engineered from the SMRTScape web app and may need cleanup/hardening before publication.
