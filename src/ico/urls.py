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
    url(r'^admin/currencies/(?P<code>(\w+))/$', views.AdminCurrencyView.as_view(), name='admin-currencies-view'),
    url(r'^admin/icos/$', views.AdminIcoList.as_view(), name='admin-icos'),
    url(r'^admin/icos/(?P<ico_id>\d+)/$', views.AdminIcoView.as_view(), name='admin-icos-view'),
    url(r'^admin/icos/(?P<ico_id>\d+)/phases/$', views.AdminPhasesList.as_view(), name='admin-phases'),
    url(r'^admin/icos/(?P<ico_id>\d+)/phases/(?P<phase_id>\d+)/$', views.AdminPhasesView.as_view(), name='admin-phases-view'),
    url(r'^admin/icos/(?P<ico_id>\d+)/phases/(?P<phase_id>\d+)/rates/$', views.AdminRatesList.as_view(), name='admin-rates'),
    url(r'^admin/icos/(?P<ico_id>\d+)/phases/(?P<phase_id>\d+)/rates/(?P<rate_id>\d+)/$', views.AdminRatesView.as_view(), name='admin-rates-view'),
    url(r'^admin/icos/(?P<ico_id>\d+)/quotes/$', views.AdminQuotesList.as_view(), name='admin-quotes'),
    url(r'^admin/icos/(?P<ico_id>\d+)/quotes/(?P<quote_id>\d+)/$', views.AdminQuotesView.as_view(), name='admin-quotes-view'),
    url(r'^admin/icos/(?P<ico_id>\d+)/purchases/$', views.AdminPurchasesList.as_view(), name='admin-purchases'),
    url(r'^admin/icos/(?P<ico_id>\d+)/purchases/(?P<purchase_id>\d+)/$', views.AdminPurchasesView.as_view(), name='admin-purchases-view'),

    # url(r'^user/icos/$', views.UserIcoList.as_view(), name='user-icos'),
    # url(r'^user/icos/(?P<ico_id>\d+)/$', views.UserIcoView.as_view(), name='user-icos-view'),
    # url(r'^user/icos/(?P<ico_id>\d+)/quotes/$', views.UserQuotesList.as_view(), name='user-quotes'),
    # url(r'^user/icos/(?P<ico_id>\d+)/quotes/(?P<quote_id>\d+)/$', views.UserQuotesView.as_view(), name='user-quotes-view'),
    # url(r'^user/icos/(?P<ico_id>\d+)/purchases/$', views.UserPurchasesList.as_view(), name='user-purchases'),
    # url(r'^user/icos/(?P<ico_id>\d+)/purchases/(?P<purchase_id>\d+)/$', views.UserPurchasesView.as_view(), name='user-purchases-view'),
)

urlpatterns = format_suffix_patterns(urlpatterns)
