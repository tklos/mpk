from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView


urlpatterns = [
    path('', RedirectView.as_view(pattern_name='mpk:home'), name='index'),
    path('mpk/', include('mpk.apps.mpk.urls')),

    # path('admin/', admin.site.urls),
]

if settings.LOCAL_MEDIA_SERVE:
    from django.conf.urls.static import static
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

