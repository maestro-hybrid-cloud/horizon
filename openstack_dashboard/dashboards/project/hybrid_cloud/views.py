from horizon import tabs
from horizon import views
from openstack_dashboard.dashboards.project.hybrid_cloud import tabs as hybrid_cloud_tabs

class IndexView(tabs.TabbedTableView):
    tab_group_class = hybrid_cloud_tabs.HybridCloudTabs
    template_name = 'project/hybrid_cloud/index.html'

    def get_data(self, request, context, *args, **kwargs):
        # Add data to the context here...
        return context
