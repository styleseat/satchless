from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from ..core.app import SatchlessApp
from . import models

class OrderApp(SatchlessApp):
    app_name = 'order'
    namespace = 'order'
    order_model = models.Order

order_app = OrderApp()
