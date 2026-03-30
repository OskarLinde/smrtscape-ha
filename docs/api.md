# SMRTScape API notes

Reverse-engineered from the SMRTScape web UI at `https://smrtscape.com`.

## Base URL

- Production UI/API host: `https://smrtscape.com`
- API prefix: `/api/v1`

## Authentication

Authentication appears to be a straightforward email/password login that returns a bearer token.

### Login

The earlier assumption about a direct JSON login endpoint was wrong.

From the compiled frontend JavaScript, the login service appears to use an API request with this authorization shape:

```http
Authorization: Basic ?email=<encoded_email>&password=<password>
```

And the SPA's general authenticated requests use:

```http
Authorization: Basic ?id=<user_id>&token=<token>
```

The web `/welcome` form also exists and may establish browser session state, but the strongest evidence from the frontend code is that the SPA login path is implemented through a custom Basic-style authorization header rather than a normal JSON login payload.

Observed login-related frontend behavior:
- user service method: `loginUser(email, password)`
- uses `apiRequestWithBasicAuth(...)`
- method shown in compiled code: `GET`
- login success stores:
  - `currentUser`
  - `accessToken = e.Token`
  - `userId = e.Id`

Open question:
- the exact login URL still needs to be pinned down from the minified bundle, but the header scheme is now much clearer.

### Authenticated requests

Subsequent API requests do not appear to use a standard bearer token.

From the compiled SPA code, the app constructs authorization like this:

```http
Authorization: Basic ?id=<user_id>&token=<token>
Content-Type: application/json
Accept: application/json
```

For login itself, the SPA code also uses a nonstandard Basic-style header:

```http
Authorization: Basic ?email=<encoded_email>&password=<password>
```

Important corrections:
- using `Authorization: Bearer <token>` is wrong
- using the raw token alone is also wrong for normal API calls
- the compiled frontend indicates the expected format is `Basic ?id=<user_id>&token=<token>`

Observed browser behavior suggests a combination of authenticated web session + this custom authorization-header scheme.

## Discovery flow

### 1) Login
Get the user object and administered account IDs.

### 2) Account details
`GET /api/v1/accounts/{account_id}?detailed=true`

Purpose:
- fetch account detail
- identify available locations

Observed useful fields:
- `_locations`
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
- `ConnectedDevice`
- `SceneScheduleSummaryList`
- `Themes`
- `DeviceGroups`

## Scene endpoints

### List scenes for a location
`GET /api/v1/scenes/byLocation/{location_id}`

Observed scene fields:
- `Id`
- `Name`
- `Description`
- `LocationId`
- `AccountId`
- `OrdinalPosition`
- `Metaphor`

### Get scene status for a location
`GET /api/v1/scenes/status/byLocation/{location_id}`

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

### Get human-readable schedule summaries
There may be a standalone endpoint, but the browser also receives schedule summary data embedded in:

`GET /api/v1/locations/{location_id}?detailed=true&includeSceneScheduleSummary=true`

Observed field on the location payload:
- `SceneScheduleSummaryList`

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

Observed directly from browser interaction.

Examples:

Turn on:
```http
PUT /api/v1/scenes/41244/force?action=on&duration=0
Authorization: Bearer <token>
```

Turn off:
```http
PUT /api/v1/scenes/41244/force?action=off&duration=0
Authorization: Bearer <token>
```

Interpretation:
- `action` is explicit on/off
- `duration=0` appears to mean immediate manual force with no explicit timer
- nonzero duration is not yet verified

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

This is useful for reverse engineering, but a Home Assistant integration should ignore browser storage and instead authenticate directly through the login endpoint.

## Suggested HA polling model

1. login
2. fetch first administered account
3. fetch locations for the account
4. for each location:
   - fetch scenes
   - fetch scene statuses
   - fetch schedule summaries
5. merge by scene ID
6. expose each scene as a switch entity
7. on toggle, call `PUT /scenes/{scene_id}/force`

## Open questions

- exact full login response schema
- whether refresh tokens or token expiry metadata exist
- whether a single bulk endpoint can replace multiple scene reads
- whether `duration` supports timed force-on/force-off actions
- whether there are rate limits
- whether gateway-offline state affects command acceptance or only state freshness
