"""Serialize API resources to JSON-friendly dicts."""

from email_engine.models import Campaign
from leads.models import Lead


def lead_to_dict(lead: Lead) -> dict:
    return {
        "id": lead.pk,
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "email": lead.email,
        "phone_number": lead.phone_number,
        "age": lead.age,
        "description": lead.description,
        "category_id": lead.category_id,
        "agent_id": lead.agent_id,
        "date_added": lead.date_added.isoformat(),
    }


def campaign_to_dict(campaign: Campaign) -> dict:
    return {
        "id": campaign.pk,
        "name": campaign.name,
        "status": campaign.status,
        "contact_list_id": campaign.contact_list_id,
        "template_id": campaign.template_id,
        "created_at": campaign.created_at.isoformat(),
        "completed_at": campaign.completed_at.isoformat()
        if campaign.completed_at
        else None,
    }
