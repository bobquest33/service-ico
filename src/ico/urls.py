from django.conf.urls import patterns, url, include
from rest_framework.urlpatterns import format_suffix_patterns

from . import views

urlpatterns = (
	url(r'^$', views.root),
    url(r'^activate/$', views.ActivateView.as_view(), name='activate'),
    url(r'^deactivate/$', views.DeactivateView.as_view(), name='deactivate'),
    url(r'^admin/webhook/$', views.WebhookView.as_view(), name='webhook'),
    url(r'^admin/company/$', views.CompanyView.as_view(), name='company')
)

urlpatterns = format_suffix_patterns(urlpatterns)
