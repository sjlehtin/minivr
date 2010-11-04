from django.conf.urls.defaults import *
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('minivr.views',
    (r'^$',                                            'index'),
    (r'^minivr/$',                                     'index'),
    (r'^minivr/route/$',                               'get_route'),
    (r'^minivr/service/(?P<service_id>\d+)/$',         'service_detail'),
    (r'^minivr/service/(?P<service_id>\d+)/reserve/$', 'service_reserve'),
    (r'^minivr/service/(?P<service_id>\d+)/reserve-simple/$', 'service_reserve_simple'))

urlpatterns += patterns('',
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),
    (r'^admin/', include(admin.site.urls)),
)
