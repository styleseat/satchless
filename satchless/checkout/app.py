from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST

from ..cart.models import Cart, user_is_authenticated
from ..order import handler
from ..order.exceptions import EmptyCart
from ..order.models import Order
from ..order.signals import order_pre_confirm
from ..payment import PaymentFailure
from ..core.app import SatchlessApp

class CheckoutApp(SatchlessApp):
    app_name = 'checkout'
    namespace = 'checkout'
    cart_model = Cart
    cart_type = 'cart'
    order_model = Order

    def checkout(self, request, order_token):
        raise NotImplementedError()
