# -*- coding: utf-8 -*-
from django.conf import settings
from django.http import HttpResponse
from django.test import (
    Client,
    TestCase,
)
from satchless.cart.tests import TestCart

from ...cart.models import CART_SESSION_KEY
from ...order.app import order_app
from ...pricing import handler as pricing_handler
from ...product.tests import DeadParrot
from ...product.tests.pricing import FiveZlotyPriceHandler
from ...order.tests import TestOrder
from ..app import CheckoutApp

class BaseCheckoutAppTests(TestCase):
    def _create_cart(self, client):
        cart = self._get_or_create_cart_for_client(client)
        cart.replace_item(self.macaw_blue, 1)
        return cart

    def _get_or_create_cart_for_client(self, client=None, typ='cart'):
        try:
            return TestCart.objects.get(
                pk=client.session[CART_SESSION_KEY % typ])[0]
        except KeyError:
            cart = TestCart.objects.create(typ=typ)
            client.session[CART_SESSION_KEY % typ] = cart.pk
            return cart

    def _get_or_create_order_for_client(self, client):
        order_pk = client.session.get('satchless_order', None)
        return self.checkout_app.order_model.objects.get(pk=order_pk)

    def _create_order(self, client):
        self._create_cart(client)
        return self._get_order_from_session(client.session)

    def _get_order_from_session(self, session):
        order_pk = session.get('satchless_order', None)
        if order_pk:
            return self.checkout_app.order_model.objects.get(pk=order_pk)
        return None

    def _get_order_items(self, order):
        order_items = set()
        for group in order.groups.all():
            order_items.update(group.items.values_list('product_variant',
                                                       'quantity'))
        return order_items


class MockCheckoutApp(CheckoutApp):

    cart_model = TestCart
    order_model = TestOrder

    def checkout(self, *args, **kwargs):
        return HttpResponse()


class App(BaseCheckoutAppTests):
    checkout_app = MockCheckoutApp()

    def setUp(self):
        self.anon_client = Client()
        self.macaw = DeadParrot.objects.create(slug='macaw',
                species="Hyacinth Macaw")
        self.macaw_blue = self.macaw.variants.create(color='blue',
                                                     looks_alive=False)
        self.original_handlers = settings.SATCHLESS_PRICING_HANDLERS
        pricing_handler.pricing_queue = pricing_handler.PricingQueue(FiveZlotyPriceHandler)

    def tearDown(self):
        pricing_handler.pricing_queue = pricing_handler.PricingQueue(*self.original_handlers)
