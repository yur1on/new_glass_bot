from django.contrib.admin import AdminSite
from panel.admin_backup import BackupAdminSiteMixin


class MyAdminSite(BackupAdminSiteMixin, AdminSite):
    site_header = "Yur1on Platform Admin"
    site_title = "Yur1on Admin"
    index_title = "Dashboard"


admin_site = MyAdminSite(name="myadmin")
