from django.utils.translation import ugettext_lazy as _

import horizon
from openstack_dashboard.dashboards.project import dashboard

class Hybrid_Cloud(horizon.Panel):
    name = _("Hybrid Cloud")
    slug = "hybrid_cloud"


dashboard.Project.register(Hybrid_Cloud)
