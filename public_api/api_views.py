from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404

from email_engine.models import Campaign, EmailTemplate
from leads.models import Agent, Category, ContactList, Lead
from public_api.auth import APIError, TokenAuthView, parse_json_body
from public_api.schema import OPENAPI_SCHEMA
from public_api.serializers import campaign_to_dict, lead_to_dict


class OpenAPISchemaView(TokenAuthView):
    def get(self, request):
        return JsonResponse(OPENAPI_SCHEMA)


class LeadListCreateAPI(TokenAuthView):
    def get(self, request):
        org = request.api_organisation
        leads = Lead.objects.for_org(org).order_by("-date_added")[:200]
        return JsonResponse({"results": [lead_to_dict(lead) for lead in leads]})

    def post(self, request):
        org = request.api_organisation
        data = parse_json_body(request)
        lead = Lead.objects.create(
            organisation=org,
            first_name=(data.get("first_name") or "").strip()[:20],
            last_name=(data.get("last_name") or "").strip()[:20],
            email=(data.get("email") or "").strip(),
            phone_number=(data.get("phone_number") or "").strip()[:20],
            age=int(data.get("age") or 0),
            description=(data.get("description") or "").strip() or "API",
        )
        if not lead.first_name or not lead.last_name or not lead.email:
            lead.delete()
            raise APIError("first_name, last_name, and email are required.")
        agent_id = data.get("agent_id")
        if agent_id:
            lead.agent = get_object_or_404(Agent, pk=agent_id, organisation=org)
            lead.save(update_fields=["agent"])
        category_id = data.get("category_id")
        if category_id:
            lead.category = get_object_or_404(
                Category, pk=category_id, organisation=org
            )
            lead.save(update_fields=["category"])
        from leads.assignment import maybe_auto_assign

        maybe_auto_assign(lead)
        return JsonResponse(lead_to_dict(lead), status=201)


class LeadDetailAPI(TokenAuthView):
    def _lead(self, request, pk):
        return get_object_or_404(
            Lead.objects.for_org(request.api_organisation), pk=pk
        )

    def get(self, request, pk):
        return JsonResponse(lead_to_dict(self._lead(request, pk)))

    def patch(self, request, pk):
        lead = self._lead(request, pk)
        data = parse_json_body(request)
        for field in ("first_name", "last_name", "email", "phone_number", "description"):
            if field in data:
                setattr(lead, field, str(data[field]).strip())
        if "age" in data:
            lead.age = int(data["age"] or 0)
        if "agent_id" in data:
            if data["agent_id"] in (None, ""):
                lead.agent = None
            else:
                lead.agent = get_object_or_404(
                    Agent, pk=data["agent_id"], organisation=request.api_organisation
                )
        if "category_id" in data:
            if data["category_id"] in (None, ""):
                lead.category = None
            else:
                lead.category = get_object_or_404(
                    Category,
                    pk=data["category_id"],
                    organisation=request.api_organisation,
                )
        lead.save()
        return JsonResponse(lead_to_dict(lead))

    def delete(self, request, pk):
        lead = self._lead(request, pk)
        lead.delete()
        return HttpResponse(status=204)


class CampaignListCreateAPI(TokenAuthView):
    def get(self, request):
        org = request.api_organisation
        campaigns = Campaign.objects.filter(organisation=org).order_by("-created_at")[
            :100
        ]
        return JsonResponse(
            {"results": [campaign_to_dict(c) for c in campaigns]}
        )

    def post(self, request):
        org = request.api_organisation
        data = parse_json_body(request)
        name = (data.get("name") or "").strip()
        if not name:
            raise APIError("name is required.")
        contact_list_id = data.get("contact_list_id")
        template_id = data.get("template_id")
        if not contact_list_id or not template_id:
            raise APIError("contact_list_id and template_id are required.")
        contact_list = get_object_or_404(
            ContactList, pk=contact_list_id, organisation=org
        )
        template = get_object_or_404(
            EmailTemplate, pk=template_id, organisation=org
        )
        campaign = Campaign.objects.create(
            organisation=org,
            name=name[:120],
            contact_list=contact_list,
            template=template,
            status=Campaign.Status.DRAFT,
            created_by=None,
        )
        return JsonResponse(campaign_to_dict(campaign), status=201)


class CampaignDetailAPI(TokenAuthView):
    def get(self, request, pk):
        campaign = get_object_or_404(
            Campaign, pk=pk, organisation=request.api_organisation
        )
        return JsonResponse(campaign_to_dict(campaign))
