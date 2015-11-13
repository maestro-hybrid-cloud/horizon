from django.conf.urls import patterns
from django.conf.urls import url


from openstack_dashboard.dashboards.project.hybrid_cloud import views

urlpatterns = patterns(
    'openstack_dashboard.dashboards.project.hybrid_cloud.views',
    url(r'^$', views.HybridTopologyView.as_view(), name='index'),
    url(r'^router$', views.RouterView.as_view(), name='router'),
    url(r'^network$', views.NetworkView.as_view(), name='network'),
    url(r'^instance$', views.InstanceView.as_view(), name='instance'),
    url(r'^router/(?P<router_id>[^/]+)/$', views.RouterDetailView.as_view(),
        name='detail'),
    url(r'^router/(?P<router_id>[^/]+)/addinterface$',
        views.NTAddInterfaceView.as_view(), name='interface'),
    url(r'^network/(?P<network_id>[^/]+)/$', views.NetworkDetailView.as_view(),
        name='detail'),
    url(r'^network/(?P<network_id>[^/]+)/subnet/create$',
        views.NTCreateSubnetView.as_view(), name='subnet'),
    url(r'^json$', views.JSONView.as_view(), name='json'),
    url(r'^launchinstance$', views.NTLaunchInstanceView.as_view(),
        name='launchinstance'),
    url(r'^createnetwork$', views.NTCreateNetworkView.as_view(),
        name='createnetwork'),
    url(r'^createrouter$', views.NTCreateRouterView.as_view(),
        name='createrouter'),
    url(r'^testview$', views.TestView.as_view(),
        name='testview'),
)
