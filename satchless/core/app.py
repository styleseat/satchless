try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from django.shortcuts import redirect

class SatchlessApp(object):
    app_name = None
    namespace = None

    def __init__(self, name=None):
        self.app_name = name or self.app_name
