from django.conf.urls import patterns
from django.conf.urls import url

from openstack_dashboard.dashboards.project.hybrid_cloud.views \
    import IndexView


urlpatterns = patterns(
    'openstack_dashboard.dashboards.project.hybrid_cloud.views',
    url(r'^$', IndexView.as_view(), name='index'),
)
