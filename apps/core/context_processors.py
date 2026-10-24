from django.conf import settings

from .versioning import display_version, get_version


def gpverse(request):
    return {
        "GP_PRODUCT": settings.GPVERSE_PRODUCT,
        "GP_VERSION": get_version(),
        "GP_VERSION_LABEL": display_version(),
    }
