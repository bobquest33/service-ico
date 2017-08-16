import datetime
import uuid

from enumfields import EnumField
from django.db import models
from django.utils.timezone import utc
from django.template import Template
from django.template import Context

from notifications.enums import WebhookEvent
from notifications.utils import common

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


class User(DateModel):
    identifier = models.UUIDField()
    token = models.CharField(max_length=200, null=True)

    def __str__(self):
        return str(self.identifier)


class Company(DateModel):
    owner = models.OneToOneField(User)
    identifier = models.CharField(max_length=100, unique=True, db_index=True)
    secret = models.UUIDField()
    email = models.EmailField(null=True, blank=True)
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

class Notification(DateModel):
    company = models.ForeignKey(Company)
    name = models.CharField(max_length=250)
    subject = models.CharField(max_length=250)
    text_message = models.TextField(null=True, blank=True)
    html_message = models.TextField(null=True, blank=True)
    sms_message = models.CharField(max_length=300, null=True, blank=True)
    enabled = models.BooleanField(default=True)
    event = EnumField(WebhookEvent, max_length=100, null=True)
    to_email = models.CharField(max_length=150, null=True, blank=True)
    to_mobile = models.CharField(max_length=150, null=True, blank=True)
    expression = models.CharField(max_length=150, null=True, blank=True)

    def __str__(self):
        return self.name

    def trigger(self, data):
        """
        Trigger emails and SMSes for a specific notification.
        """

        # Evaluate whether the notification should trigger.
        if self.expression and not common.evaluate(self.expression, data):
            return

        # Populate the subject, email and mobile fields
        subject = Template(self.subject).render(Context(data))
        email = Template(self.to_email).render(Context(data))
        mobile = Template(self.to_mobile).render(Context(data))

        if not subject or (not email and not mobile):
            return

        messages = self.build_messages(data)

        # If email is valid and a text message exists.
        if common.validate_email(email) and messages.get('text'):
            log_data = {"notification": self,
                        "recipient": email,
                        "text_message": messages.get('sms'),
                        "html_message": messages.get('html')}

            try:
                common.send_email(
                    subject, 
                    messages.get('text'),
                    email, 
                    from_email=self.company.get_from_email(), 
                    html_message=messages.get('html'))
            except Exception as exc:
                # Add error to the logs.
                log_data.update({"error_message": str(exc), "sent": False})

            # Log message
            NotificationLog.objects.create(**log_data)

        # If mobile is valid and sms message exists
        if common.validate_mobile(mobile) and messages.get('sms'):
            log_data = {"notification": self,
                        "recipient": mobile,
                        "sms_message": messages.get('sms')}

            try:
                common.send_sms(messages.get('sms'), mobile)
            except Exception as exc:
                # Add error to the logs.
                log_data.update({"error_message": str(exc), "sent": False})

            # Log Message
            NotificationLog.objects.create(**log_data)

    def build_messages(self, data):
        """
        Build email and SMS messages using the custom templates and webhook 
        data.
        """

        messages = {}

        if self.text_message:
            messages['text'] = Template(self.text_message).render(Context(data))

        if self.html_message:
            messages['html'] = Template(self.html_message).render(Context(data))

        if self.sms_message:
            messages['sms'] = Template(self.sms_message).render(Context(data))

        return messages


class NotificationLog(DateModel):
    notification = models.ForeignKey(Notification)
    recipient = models.CharField(max_length=150)
    text_message = models.TextField(null=True)
    html_message = models.TextField(null=True)
    sms_message = models.CharField(max_length=300, null=True)
    sent = models.BooleanField(default=True)
    error_message = models.TextField(null=True)

    def __str__(self):
        return '%s: %s' % (self.notification, self.error_message)
