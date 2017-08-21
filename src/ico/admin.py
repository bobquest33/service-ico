from django.contrib import admin
from ico.models import *

admin.site.register(User)
admin.site.register(Company)
admin.site.register(Currency)
admin.site.register(Ico)
admin.site.register(Phase)
admin.site.register(Rate)
admin.site.register(Quote)
admin.site.register(Purchase)