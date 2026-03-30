# SMRTScape API notes

Reverse-engineered from the SMRTScape web UI at `https://smrtscape.com` and validated against one working account/location.

## Base URL

- Production UI/API host: `https://smrtscape.com`
- API prefix: `/api/v1`

## Authentication

SMRTScape does **not** use a standard bearer-token API flow.

From the compiled frontend bundle, login and subsequent API calls use custom `Authorization` header formats.

### Login request

The SPA login flow calls:

`GET /api/v1/users?detailed=true`

with a header like:

```http
Authorization: Basic ?email=<encoded_email>&password=<password>
Accept: application/json, text/plain, */*
X-Requested-With: XMLHttpRequest
```

Notes:
- email encoding in the frontend at minimum replaces `+` with `%2b`
- the response is a user object, not just a token blob
- successful response includes both `Id` and `Token`

Observed login-related frontend behavior from the compiled bundle:
- service method: `loginUser(email, password)`
- uses `apiRequestWithBasicAuth(...)`
- request method shown in compiled code: `GET`
- on success, frontend stores:
  - `currentUser`
  - `accessToken = e.Token`
  - `userId = e.Id`

### Authenticated API requests

After login, the SPA uses:

```http
Authorization: Basic ?id=<user_id>&token=<token>
Content-Type: application/json
Accept: application/json
X-Requested-With: XMLHttpRequest
```

Important corrections from earlier assumptions:
- `Authorization: Bearer <token>` is wrong
- raw token alone is wrong for normal API requests
- the compiled frontend indicates `Basic ?id=<user_id>&token=<token>` is the intended auth shape

## Discovery flow

### 1) Login
Fetch the user object from:

`GET /api/v1/users?detailed=true`

Useful fields observed on the response:
- `Id`
- `Email`
- `Token`
- `AccountsAdministered`
- `OrganizationsAdministered`

### 2) Account details
`GET /api/v1/accounts/{account_id}?detailed=true`

Purpose:
- fetch account detail
- identify available locations

Observed useful fields:
- `Locations`
- `ConnectedDevices`
- organization/account metadata

### 3) Location details
`GET /api/v1/locations/{location_id}?detailed=true&includeSceneScheduleSummary=true`

Purpose:
- fetch location detail
- connected gateway/device metadata
- schedule summaries and related information

Observed useful fields:
- `Id`
- `Name`
- `Description`
- `Latitude` / `Longitude`
- `ConnectedDevices`
- `SceneScheduleSummaryList`
- `Themes`
- `DeviceGroups`

## Scene endpoints

### List scenes for a location
`GET /api/v1/scenes/byLocation/{location_id}`

Observed response shape:

```json
{
  "SceneScheduleSummaryList": [...],
  "Scenes": [...]
}
```

Observed scene fields:
- `Id`
- `Name`
- `Description`
- `LocationId`
- `AccountId`
- `OrdinalPosition`
- `Metaphor`
- `ImageId`
- `ImageAssetId`
- `WhenImageCreated`
- `WhenImageLastUpdated`
- `ImageAsset`

### Get scene status for a location
`GET /api/v1/scenes/status/byLocation/{location_id}`

Observed response shape:
- JSON array of scene status objects

Purpose:
- current scene state
- schedule state
- gateway online/offline state
- next transitions

Observed fields:
- `SceneId`
- `IsSceneOn`
- `IsSceneForcedOn`
- `IsSceneForcedOff`
- `IsSceneScheduledOn`
- `IsSceneOffDueToForceOnExpiration`
- `IsGatewayOnline`
- `CurrentSceneTime`
- `WhenSceneForceReleased`
- `NextScheduledOnTime`
- `NextScheduledOffTime`
- `LastScheduledOnTime`
- `LastScheduledOffTime`
- `LastSceneForceOnTime`
- `LastSceneForceOffTime`
- `SceneDstOffset`
- `StatusText`
- `NextStatusText`
- `TroubleshootingInfo`

### Scene image metadata
When a scene has an uploaded image, the scene payload may include:

- `ImageId`
- `ImageAssetId`
- `WhenImageCreated`
- `WhenImageLastUpdated`
- `ImageAsset`
  - `Id`
  - `Uid`
  - `ImageAssetItems[]`
    - `Uri`
    - `Name`
    - `Width`
    - `Height`
    - `WhenCreated`

Observed behavior:
- the blob `Uri` is publicly reachable
- but storage may return `application/octet-stream` instead of a specific image MIME type
- the Home Assistant integration therefore fetches image bytes directly and infers image type when needed
- the integration caches image bytes in memory and invalidates the cache when URL or image-update metadata changes

### Schedule summary data
Schedule summary data is available on both:
- `GET /api/v1/locations/{location_id}?detailed=true&includeSceneScheduleSummary=true`
- and also in the wrapper returned by `GET /api/v1/scenes/byLocation/{location_id}`

Observed summary fields:
- `Id`
- `Schedule`

Examples:
- `Every day: Dusk–10:00 pm`
- `Every day: Dawn–10:00 pm`
- `Every day: 8:00 am–8:30 am`

## Scene control

### Force scene on/off
`PUT /api/v1/scenes/{scene_id}/force?action=on|off&duration=0`

Observed directly from browser interaction and validated through the Home Assistant integration.

Examples:

Turn on:
```http
PUT /api/v1/scenes/41244/force?action=on&duration=0
Authorization: Basic ?id=<user_id>&token=<token>
```

Turn off:
```http
PUT /api/v1/scenes/41244/force?action=off&duration=0
Authorization: Basic ?id=<user_id>&token=<token>
```

Interpretation:
- `action` is explicit on/off
- `duration=0` means non-timed force on/off behavior
- nonzero duration likely supports temporary/timed force-on, but that has not been formally implemented in the HA integration

### Gateway offline behavior
If the gateway is offline, the cloud may return HTTP 500 on force requests with a message like:

- `Cannot perform the requested operation, the gateway is not communicating.`

The HA integration maps this to a cleaner user-facing error:
- `Gateway offline`

## Observed account/location example

Observed in one real account:
- account: `Residence`
- location: `House`
- gateway: `201-352-198`
- scenes:
  - `39200` — Light around the house
  - `39201` — Playground and lower
  - `41244` — Front fountain
  - `41246` — Creek

## Browser storage observations

The SPA stores substantial state in `localStorage`, including:
- `AccessToken`
- `CurrentUser`
- `authState`
- `locationState`
- `lightingState`

Session storage also held:
- `WhatsNewClosed=true`

This was useful for reverse engineering, but the Home Assistant integration authenticates directly with the API rather than relying on browser storage.

## Current HA integration model

1. login via `GET /api/v1/users?detailed=true` using the custom login header
2. read first administered account from the user object
3. fetch account detail
4. fetch locations
5. for each location:
   - fetch location detail
   - fetch scenes wrapper
   - fetch scene statuses
6. merge scene metadata + status + schedule summary by scene ID
7. expose each scene as a switch entity
8. expose scene status/next-status as sensors
9. expose gateway online/offline as a binary sensor

## Open questions

- whether Toro may change the auth-header scheme in the web app
- whether nonzero `duration` values support exactly the app’s timed-on behavior
- whether there are rate limits worth explicitly handling
- whether there are additional bulk endpoints worth using later
