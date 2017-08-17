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
    url(r'^admin/currencies/(?P<code>.*)/$', views.AdminCurrencyView.as_view(), name='admin-currencies-view'),

    url(r'^admin/icos/$', views.AdminIcoList.as_view(), name='admin-icos'),
    url(r'^admin/icos/(?P<ico_id>.*)/$', views.AdminIcoView.as_view(), name='admin-icos-view'),

    url(r'^admin/icos/(?P<ico_id>.*)/phases/$', views.AdminPhasesList.as_view(), name='admin-phases'),
    url(r'^admin/icos/(?P<ico_id>.*)/phases/(?P<phase_id>.*)/$', views.AdminPhasesView.as_view(), name='admin-phases-view'),

    url(r'^admin/icos/(?P<ico_id>.*)/phases/(?P<phase_id>.*)/rates/$', views.AdminRatesList.as_view(), name='admin-rates'),
    url(r'^admin/icos/(?P<ico_id>.*)/phases/(?P<phase_id>.*)/rates/(?P<rate_id>.*)/$', views.AdminRatesView.as_view(), name='admin-rates-view'),

    #url(r'^admin/icos/(?P<ico_id>.*)/quotes/$', views.AdminQuotesList.as_view(), name='admin-quotes'),
    #url(r'^admin/icos/(?P<ico_id>.*)/quotes/(?P<currency_id>.*)/$', views.AdminQuotesView.as_view(), name='admin-quotes-view'),

    #url(r'^admin/icos/(?P<ico_id>.*)/purchases/$', views.AdminPurchasesList.as_view(), name='admin-purchases'),
    #url(r'^admin/icos/(?P<ico_id>.*)/purchases/(?P<currency_id>.*)/$', views.AdminPurchasesView.as_view(), name='admin-purchases-view'),
)

urlpatterns = format_suffix_patterns(urlpatterns)
