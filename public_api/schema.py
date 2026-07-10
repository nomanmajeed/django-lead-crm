"""OpenAPI 3.0 schema for the public API."""

OPENAPI_SCHEMA = {
    "openapi": "3.0.3",
    "info": {
        "title": "Lead CRM Public API",
        "version": "1.0.0",
        "description": "Org-scoped REST API authenticated with Bearer tokens.",
    },
    "servers": [{"url": "/api/v1"}],
    "components": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
            }
        }
    },
    "security": [{"bearerAuth": []}],
    "paths": {
        "/leads/": {
            "get": {"summary": "List leads", "responses": {"200": {"description": "OK"}}},
            "post": {"summary": "Create lead", "responses": {"201": {"description": "Created"}}},
        },
        "/leads/{id}/": {
            "get": {"summary": "Retrieve lead"},
            "patch": {"summary": "Update lead"},
            "delete": {"summary": "Delete lead"},
        },
        "/campaigns/": {
            "get": {"summary": "List campaigns"},
            "post": {"summary": "Create draft campaign"},
        },
        "/campaigns/{id}/": {"get": {"summary": "Retrieve campaign"}},
    },
}
