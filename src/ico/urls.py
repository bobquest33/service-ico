from django.conf.urls import patterns, url, include
from rest_framework.urlpatterns import format_suffix_patterns

from . import views

urlpatterns = (
	url(r'^$', views.root),
    url(r'^activate/$', views.ActivateView.as_view(), name='activate'),
    url(r'^deactivate/$', views.DeactivateView.as_view(), name='deactivate'),
    url(r'^admin/webhook/$', views.AdminWebhookView.as_view(), name='admin-webhook'),
    url(r'^admin/company/$', views.AdminCompanyView.as_view(), name='admin-company'),
    url(r'^admin/currencies/$', views.AdminCurrencyList.as_view(), name='admin-currencies'),
    url(r'^admin/icos/$', views.AdminIcoList.as_view(), name='admin-icos'),
    url(r'^admin/icos/(?P<ico_id>.*)/$', views.AdminIcoView.as_view(), name='admin-icos-view'),
)

urlpatterns = format_suffix_patterns(urlpatterns)
