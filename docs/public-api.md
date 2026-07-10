# Lead CRM Public API

Org-scoped REST API authenticated with Bearer tokens. Each token is tied to one organisation; cross-tenant access is not possible.

## Authentication

```http
Authorization: Bearer <your-api-token>
```

Create tokens in the app under **API tokens** (`/app/api/tokens/`). The raw token is shown once at creation.

## Base URL

```
/api/v1/
```

## Leads

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/leads/` | List leads (max 200) |
| POST | `/api/v1/leads/` | Create lead |
| GET | `/api/v1/leads/{id}/` | Retrieve lead |
| PATCH | `/api/v1/leads/{id}/` | Update lead |
| DELETE | `/api/v1/leads/{id}/` | Delete lead |

### Create lead (JSON)

```json
{
  "first_name": "Ada",
  "last_name": "Lovelace",
  "email": "ada@example.com",
  "phone_number": "555-0100",
  "description": "From integration",
  "age": 30,
  "agent_id": null,
  "category_id": null
}
```

## Campaigns (limited)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/campaigns/` | List campaigns |
| POST | `/api/v1/campaigns/` | Create **draft** campaign |
| GET | `/api/v1/campaigns/{id}/` | Retrieve campaign |

### Create draft campaign

```json
{
  "name": "API blast",
  "contact_list_id": 1,
  "template_id": 1
}
```

Send/schedule campaigns from the organiser UI after creation.

## Schema

OpenAPI 3.0 JSON (requires valid Bearer token):

```
GET /api/v1/openapi.json
```

## Errors

Responses use `{"error": "message"}` with HTTP status `401` (auth), `400` (validation), or `404` (not found in your org).
