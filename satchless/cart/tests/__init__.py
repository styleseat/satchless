# -*- coding: utf-8 -*-


import os

from decimal import Decimal
from django.db import models as dj_models
from django.contrib.auth import (
    models as auth_models,
    get_user_model,
)
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.test import (
    Client,
    RequestFactory,
    TestCase,
)
from ...cart.models import Cart, CartItem, CART_SESSION_KEY

from ...category.models import Category
from ...pricing import (
    Price,
    handler as pricing_handler,
)
from ...product.tests.pricing import FiveZlotyPriceHandler
from ...product.tests import DeadParrot, ZombieParrot

from .. import models
from .. import signals


class TestCart(Cart):

    class Meta:
        proxy = True

    def get_cart_item_class(self):
        return TestCartItem

class TestCartItem(CartItem):
    cart = dj_models.ForeignKey(TestCart, related_name='items', on_delete=dj_models.PROTECT)


class Cart(TestCase):
    def setUp(self):
        self.category_birds = Category.objects.create(name='birds',
                                                      slug='birds')
        self.macaw = DeadParrot.objects.create(slug='macaw',
                                               species='Hyacinth Macaw')
        self.cockatoo = DeadParrot.objects.create(slug='cockatoo',
                                                  species='White Cockatoo')
        self.category_birds.products.add(self.macaw)
        self.category_birds.products.add(self.cockatoo)
        self.macaw_blue = self.macaw.variants.create(color='blue',
                                                     looks_alive=False)
        self.macaw_blue_fake = self.macaw.variants.create(color='blue',
                                                          looks_alive=True)
        self.cockatoo_white_a = self.cockatoo.variants.create(color='white',
                                                              looks_alive=True)
        self.cockatoo_white_d = self.cockatoo.variants.create(color='white',
                                                              looks_alive=False)
        self.cockatoo_blue_a = self.cockatoo.variants.create(color='blue',
                                                             looks_alive=True)
        self.cockatoo_blue_d = self.cockatoo.variants.create(color='blue',
                                                             looks_alive=False)
        # only staff users can view uncategorized products
        self.user1 = get_user_model().objects.create(username="testuser", is_staff=True,
                                         is_superuser=True)
        self.user1.set_password(u"pasło")
        self.category_birds.products.add(self.macaw)
        self.user1.save()

        self.original_pricing_queue = pricing_handler.pricing_queue
        pricing_handler.pricing_queue = pricing_handler.PricingQueue(FiveZlotyPriceHandler)

    def tearDown(self):
        pricing_handler.pricing_queue = self.original_pricing_queue

    def test_str(self):
        cart1 = TestCart(typ='satchless.test_cart1')
        self.assertEqual(str(cart1), 'satchless.test_cart1')

        cart2 = TestCart(typ='satchless.test_cart2', owner=self.user1)
        self.assertEqual(str(cart2), 'satchless.test_cart2 of testuser')

    def test_basic_cart_ops(self):
        cart = TestCart.objects.create(typ='satchless.test_cart')
        cart.replace_item(self.macaw_blue, 1)
        cart.replace_item(self.macaw_blue_fake, Decimal('2.45'))
        cart.replace_item(self.cockatoo_white_a, Decimal('2.45'))
        cart.replace_item(self.cockatoo_white_d, '4.11')
        cart.replace_item(self.cockatoo_blue_a, 6)
        cart.replace_item(self.cockatoo_blue_d, Decimal('2'))
        # remove three items
        cart.replace_item(self.cockatoo_white_d, 0)
        cart.replace_item(self.cockatoo_blue_a, Decimal('0'))
        cart.replace_item(self.cockatoo_white_a, '0.0')

        self.assertEqual(cart.get_quantity(self.macaw_blue), Decimal('1'))
        self.assertEqual(cart.get_quantity(self.macaw_blue_fake), Decimal('2'))
        self.assertEqual(cart.get_quantity(self.cockatoo_white_a), 0)
        self.assertRaises(ObjectDoesNotExist, cart.items.get,
                          variant=self.cockatoo_white_a)
        self.assertEqual(cart.get_quantity(self.cockatoo_white_d), Decimal('0'))
        self.assertRaises(ObjectDoesNotExist, cart.items.get,
                          variant=self.cockatoo_white_d)
        self.assertEqual(cart.get_quantity(self.cockatoo_blue_a), Decimal('0.0'))
        self.assertRaises(ObjectDoesNotExist, cart.items.get,
                          variant=self.cockatoo_blue_a)
        self.assertEqual(cart.get_quantity(self.cockatoo_blue_d), Decimal('2'))

        cart.add_item(self.macaw_blue, 100)
        cart.add_item(self.macaw_blue_fake, 100)
        cart.add_item(self.cockatoo_white_a, 100)
        cart.add_item(self.cockatoo_white_d, 100)
        cart.add_item(self.cockatoo_blue_a, 100)
        cart.add_item(self.cockatoo_blue_d, 100)

        self.assertEqual(cart.get_quantity(self.macaw_blue), Decimal('101'))
        self.assertEqual(cart.get_quantity(self.macaw_blue_fake), Decimal('102'))
        self.assertEqual(cart.get_quantity(self.cockatoo_white_a), Decimal('100'))
        self.assertEqual(cart.get_quantity(self.cockatoo_white_d), Decimal('100'))
        self.assertEqual(cart.get_quantity(self.cockatoo_blue_a), Decimal('100'))
        self.assertEqual(cart.get_quantity(self.cockatoo_blue_d), Decimal('102'))

        cart.add_item(self.macaw_blue, -101)
        self.assertEqual(cart.get_quantity(self.macaw_blue), Decimal('0'))
        self.assertEqual(cart.total(), Price(2520, currency='USD'))

    def _get_or_create_cart_for_client(self, client=None, typ='cart'):
        try:
            return TestCart.objects.get(
                pk=client.session[CART_SESSION_KEY % typ])[0]
        except KeyError:
            cart = TestCart.objects.create(typ=typ)
            client.session[CART_SESSION_KEY % typ] = cart.pk
            return cart

    def test_signals(self):
        def modify_qty(sender, instance=None, variant=None, old_quantity=None,
                       new_quantity=None, result=None, **kwargs):
            if instance.typ != 'satchless.test_cart_with_signals':
                return
            if variant.product == self.macaw:
                result.append((Decimal('0'), u"Out of stock"))
            elif not variant.looks_alive:
                result.append((Decimal('1'), u"Parrots don't rest in groups"))

        cart = TestCart.objects.create(typ='satchless.test_cart_with_signals')
        signals.cart_quantity_change_check.connect(modify_qty)
        result = cart.replace_item(self.macaw_blue, 10, dry_run=True)
        self.assertEqual((result.new_quantity, result.reason),
                         (0, u"Out of stock"))
        self.assertEqual(0, cart.get_quantity(self.macaw_blue))
        result = cart.replace_item(self.macaw_blue, 10)
        self.assertEqual((result.new_quantity, result.reason),
                         (0, u"Out of stock"))
        self.assertEqual(0, cart.get_quantity(self.macaw_blue))
        result = cart.add_item(self.macaw_blue, 10)
        self.assertEqual((result.new_quantity, result.quantity_delta,
                          result.reason),
                         (0, 0, u"Out of stock"))
        self.assertEqual(0, cart.get_quantity(self.macaw_blue))
        result = cart.replace_item(self.cockatoo_white_d, 10, dry_run=True)
        self.assertEqual((result.new_quantity, result.reason),
                         (1, u"Parrots don't rest in groups"))
        self.assertEqual(0, cart.get_quantity(self.cockatoo_white_d))
        result = cart.replace_item(self.cockatoo_white_d, 10)
        self.assertEqual((result.new_quantity, result.reason),
                         (1, u"Parrots don't rest in groups"))
        self.assertEqual(1, cart.get_quantity(self.cockatoo_white_d))
        result = cart.add_item(self.cockatoo_white_d, 10)
        self.assertEqual((result.new_quantity,
                          result.quantity_delta,
                          result.reason),
                         (1, 0, u"Parrots don't rest in groups"))
        self.assertEqual(1, cart.get_quantity(self.cockatoo_white_d))

    def test_get_from_request_does_not_exist_anon(self):
        request = RequestFactory()
        request.session = {}
        request.user = auth_models.AnonymousUser()
        typ = 'satchless.test_get_from_request_does_not_exist_anon'
        with self.assertRaises(TestCart.DoesNotExist):
            TestCart.objects.get_from_request(request, typ)

    def test_get_from_request_exists_anon(self):
        request = RequestFactory()
        request.session = {}
        request.user = auth_models.AnonymousUser()
        typ = 'satchless.test_get_from_request_exists_anon'
        key = '_satchless_cart-%s' % typ
        cart = TestCart.objects.create(typ=typ)
        request.session[key] = cart.pk
        self.assertEqual(
            TestCart.objects.get_from_request(request, typ),
            cart,
        )

    def test_get_from_request_does_not_exist_authenticated(self):
        request = RequestFactory()
        request.session = {}
        request.user = get_user_model().objects.create(username='testuser1')
        typ = 'satchless.test_get_from_request_does_not_exist_authenticated'
        with self.assertRaises(TestCart.DoesNotExist):
            TestCart.objects.get_from_request(request, typ)

    def test_get_from_request_exists_authenticated(self):
        request = RequestFactory()
        request.session = {}
        request.user = get_user_model().objects.create(username='testuser2')
        typ = 'satchless.test_get_from_request_exists_authenticated'
        key = '_satchless_cart-%s' % typ
        cart = TestCart.objects.create(typ=typ)
        request.session[key] = cart.pk
        new_cart = TestCart.objects.get_from_request(request, typ)
        self.assertEqual(new_cart, cart)
        self.assertEqual(new_cart.owner, request.user)

    def test_get_or_create_from_request_does_not_exist_anon(self):
        request = RequestFactory()
        request.session = {}
        request.user = auth_models.AnonymousUser()
        typ = 'satchless.test_get_or_create_from_request_does_not_exist_anon'
        cart = TestCart.objects.get_or_create_from_request(request, typ)
        self.assertIsNone(cart.owner)
        self.assertEqual(cart.typ, typ)

    def test_get_or_create_from_request_exists_anon(self):
        request = RequestFactory()
        request.session = {}
        request.user = auth_models.AnonymousUser()
        typ = 'satchless.test_get_or_create_from_request_exists_anon'
        key = '_satchless_cart-%s' % typ
        cart = TestCart.objects.create(typ=typ)
        request.session[key] = cart.pk
        self.assertEqual(
            TestCart.objects.get_or_create_from_request(request, typ),
            cart,
        )

    def test_get_or_create_from_request_does_not_exist_authenticated(self):
        request = RequestFactory()
        request.session = {}
        request.user = get_user_model().objects.create(username='testuser1')
        typ = 'satchless.test_get_or_create_from_request_does_not_exist_authenticated'
        cart = TestCart.objects.get_or_create_from_request(request, typ)
        self.assertEqual(cart.owner, request.user)
        self.assertEqual(cart.typ, typ)

    def test_get_or_create_from_request_exists_authenticated(self):
        request = RequestFactory()
        request.session = {}
        request.user = get_user_model().objects.create(username='testuser2')
        typ = 'satchless.test_get_or_create_from_request_exists_authenticated'
        key = '_satchless_cart-%s' % typ
        cart = TestCart.objects.create(typ=typ)
        request.session[key] = cart.pk
        new_cart = TestCart.objects.get_or_create_from_request(request, typ)
        self.assertEqual(new_cart, cart)
        self.assertEqual(new_cart.owner, request.user)
