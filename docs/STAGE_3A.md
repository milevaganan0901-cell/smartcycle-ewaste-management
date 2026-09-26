# Stage 3A — Device Management Backend

Stage 3A adds the real device-management foundation to the FastAPI backend:

- SQLite database access through SQLAlchemy
- `Device` model and Pydantic schemas
- Server-side yearly sequential tracking IDs
- Transparent rule-based/demo valuation service
- Device CRUD and status endpoints
- No authentication or frontend connection in this stage

## Database

The default local database is:

```text
backend/smartcycle.db
```

The location can be changed with `DATABASE_URL` in the backend environment. The database file is ignored by Git.

## Device model

The `devices` table contains:

| Field | Type | Notes |
|---|---|---|
| `id` | integer | Primary key, auto-increment |
| `tracking_id` | string | Unique, indexed, server-generated |
| `device_category` | string | Required |
| `brand` | string | Required |
| `model` | string | Required |
| `age` | integer | Required, years; must be zero or greater |
| `condition` | string | Required, such as Excellent, Good, Fair or Poor |
| `working_status` | string | Required, such as Fully Working, Partially Working or Not Working |
| `physical_damage` | string | Optional description; defaults to `None` |
| `accessories` | string | Optional comma-separated description |
| `original_purchase_price` | float | Optional; must be zero or greater |
| `location` | string | Required pickup location/city |
| `estimated_purchase_value` | float | Rule-based/demo estimate |
| `potential_refurbished_value` | float | Rule-based/demo estimate |
| `potential_recycled_value` | float | Rule-based/demo estimate |
| `status` | string | Defaults to `Submitted` |
| `created_at` | datetime | Set when the record is created |
| `updated_at` | datetime | Updated when the record changes |

Allowed lifecycle statuses:

```text
Submitted
Under Review
Pickup Scheduled
Collected
Inspection
Refurbishment
Recycling
Completed
```

## Tracking IDs

Tracking IDs are generated only by the backend. The format is:

```text
EW-YYYY-NNNN
```

The year comes from the server clock. The four-digit number is sequential within that year. The first device created in a year receives `0001`.

## Rule-based/demo valuation

The valuation service lives at:

```text
backend/app/services/valuation.py
```

It is a small, readable calculation:

1. Use the original purchase price when provided; otherwise use a category reference value.
2. Apply 12% depreciation for each year of age, with a 25% floor.
3. Apply a condition factor.
4. Apply a working-status factor.
5. Apply a physical-damage factor.
6. Keep a minimum value of 500 for visible recovery estimates.
7. Use a conservative 8% recovery ratio for the recycled-value estimate.
8. Use a refurbishment factor only for usable devices that are not in poor condition.

The service is a demonstration estimator. It is not connected to external price feeds and should be reviewed before being used for a real transaction.

## API endpoints

All device endpoints are under `/api/devices`.

### Create a device

```http
POST /api/devices
```

Example request:

```json
{
  "device_category": "Smartphone",
  "brand": "Apple",
  "model": "iPhone 13",
  "age": 2,
  "condition": "Good",
  "working_status": "Fully Working",
  "physical_damage": "Minor scratches",
  "accessories": "Original box and cable",
  "original_purchase_price": 50000,
  "location": "Bengaluru, Karnataka"
}
```

Example response (`201 Created`):

```json
{
  "id": 1,
  "tracking_id": "EW-2026-0001",
  "device_category": "Smartphone",
  "brand": "Apple",
  "model": "iPhone 13",
  "age": 2,
  "condition": "Good",
  "working_status": "Fully Working",
  "physical_damage": "Minor scratches",
  "accessories": "Original box and cable",
  "original_purchase_price": 50000.0,
  "location": "Bengaluru, Karnataka",
  "estimated_purchase_value": 34197.5,
  "potential_refurbished_value": 42746.88,
  "potential_recycled_value": 2735.8,
  "status": "Submitted",
  "created_at": "2026-09-25T12:00:00Z",
  "updated_at": "2026-09-25T12:00:00Z"
}
```

### List devices

```http
GET /api/devices
GET /api/devices?status=Inspection
```

The optional status filter accepts only the allowed lifecycle statuses.

### Get one device

```http
GET /api/devices/EW-2026-0001
```

A missing tracking ID returns `404` with a `detail` message.

### Update status

```http
PATCH /api/devices/EW-2026-0001/status
```

Request:

```json
{
  "status": "Inspection"
}
```

Only `status` and `updated_at` are changed. An unsupported status returns `422` with validation details.

### Delete a device

```http
DELETE /api/devices/EW-2026-0001
```

A successful deletion returns `204 No Content`. A subsequent lookup returns `404`.

## Out of scope for Stage 3A

- Authentication, users and roles
- Pickup requests
- Admin authorization
- Frontend API calls
- Real external pricing data
- Later processing-status integrations
