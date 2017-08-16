from django.contrib import admin
from notifications.models import *

admin.site.register(User)
admin.site.register(Company)
admin.site.register(Notification)
admin.site.register(NotificationLog)
