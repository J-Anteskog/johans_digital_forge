"""
Sitemap configuration för Johan's Digital Forge
Home finns på svenska och engelska, övriga sidor är enspråkiga
"""
import datetime
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Sitemap för alla statiska sidor"""
    changefreq = 'monthly'

    def items(self):
        return [
            'home_sv',
            'home_en',
            'privacy_policy_sv',
            'privacy_policy_en',
            'portfolio',
            'service_list',
            'contact',
            'about_us',
            'about_us_en',
            'analysis',
            'analysis_en',
            'brief',
            'brief_en',
        ]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        if item == 'home_sv':
            return 1.0
        elif item == 'home_en':
            return 0.8
        else:
            return 0.7

    def lastmod(self, item):
        return datetime.date.today()


# Om du senare har portfolio-projekt med slug/detaljsidor:
# from portfolio.models import Project
# 
# class ProjectSitemap(Sitemap):
#     """Sitemap för portfolio-projekt"""
#     changefreq = 'weekly'
#     priority = 0.9
#     
#     def items(self):
#         return Project.objects.filter(published=True).order_by('-created_at')
#     
#     def lastmod(self, obj):
#         return obj.updated_at if hasattr(obj, 'updated_at') else obj.created_at
#     
#     def location(self, obj):
#         return reverse('project_detail', args=[obj.slug])