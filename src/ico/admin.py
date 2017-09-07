from django.contrib import admin
from ico.models import *


class RateAdmin(admin.ModelAdmin):
    list_display = Rate._meta.get_all_field_names()


admin.site.register(User)
admin.site.register(Company)
admin.site.register(Currency)
admin.site.register(Ico)
admin.site.register(Phase)
admin.site.register(Rate, RateAdmin)
admin.site.register(Quote)
admin.site.register(PurchaseMessage)
admin.site.register(Purchase)
