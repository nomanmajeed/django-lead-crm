from django.db import models


class TenantQuerySet(models.QuerySet):
    def for_org(self, organisation):
        if organisation is None:
            return self.none()
        return self.filter(organisation=organisation)


class TenantManager(models.Manager):
    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)

    def for_org(self, organisation):
        return self.get_queryset().for_org(organisation)
