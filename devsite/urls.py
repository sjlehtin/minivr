from django.conf.urls.defaults import *
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    (r'^minivr/$',                                     'minivr.views.index'),
    (r'^minivr/service/(?P<service_id>\d+)/$',         'minivr.views.service_detail'),
    (r'^minivr/service/(?P<service_id>\d+)/reserve/$', 'minivr.views.service_reserve'),

    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),
    (r'^admin/', include(admin.site.urls)),
)
