import datetime
import uuid

from enumfields import EnumField
from django.db import models
from django.utils.timezone import utc
from django.template import Template
from django.template import Context

from ico.enums import WebhookEvent

from logging import getLogger

logger = getLogger('django')


class DateModel(models.Model):
    created = models.DateTimeField()
    updated = models.DateTimeField()

    class Meta:
        abstract = True

    def __str__(self):
        return str(self.created)

    def save(self, *args, **kwargs):
        if not self.id:  # On create
            self.created = datetime.datetime.now(tz=utc)

        self.updated = datetime.datetime.now(tz=utc)
        return super(DateModel, self).save(*args, **kwargs)


class Company(DateModel):
    identifier = models.CharField(max_length=100, unique=True, db_index=True)
    admin = models.OneToOneField('ico.User', related_name='admin_company')
    secret = models.UUIDField()
    name = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.identifier

    def natural_key(self):
        return (self.identifier,)

    def get_from_email(self):
        if self.email and self.name:
            return "{name} <{email}>".format(name=self.name, 
                email=self.email)
        elif self.email:
            return self.email       
        else:
            return None

    def save(self, *args, **kwargs):
        if not self.id:
            self.secret = uuid.uuid4()

        return super(Company, self).save(*args, **kwargs)


class User(DateModel):
    identifier = models.UUIDField()
    token = models.CharField(max_length=200, null=True)
    company = models.ForeignKey('ico.Company', null=True)

    def __str__(self):
        return str(self.identifier)