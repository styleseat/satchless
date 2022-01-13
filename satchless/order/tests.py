# -*- coding: utf-8 -*-
from __future__ import absolute_import
import datetime
import mock
from decimal import Decimal
from django.db import models
import os
import six

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import (
    Client,
    TestCase,
)

from ..payment import PaymentFailure
from ..payment.models import PaymentVariant
from ..payment.tests import TestPaymentType
from ..pricing import handler, Price
from ..product.tests import DeadParrot
from ..product.tests.pricing import FiveZlotyPriceHandler
from .app import order_app
from .handler import payment_queue, PaymentQueue
from .models import (
    DeliveryGroup,
    Order,
    OrderedItem,
    OrderManager,
    signals,
)
from .exceptions import EmptyCart
from ..cart.tests import TestCart

class TestOrder(Order):
    cart = models.ForeignKey(TestCart, blank=True, null=True, related_name='orders', on_delete=models.PROTECT)
    objects = OrderManager()

class OrderTest(TestCase):
    def setUp(self):
        order_app.order_model = TestOrder
        self.macaw = DeadParrot.objects.create(slug='macaw',
                species="Hyacinth Macaw")
        self.cockatoo = DeadParrot.objects.create(slug='cockatoo',
                species="White Cockatoo")
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

        self.original_handlers = settings.SATCHLESS_PRICING_HANDLERS
        handler.pricing_queue = handler.PricingQueue(FiveZlotyPriceHandler)

    def tearDown(self):
        handler.pricing_queue = handler.PricingQueue(*self.original_handlers)

    def test_get_from_empty_cart_raises(self):
        cart = TestCart.objects.create(typ='satchless.test_cart')
        with self.assertRaises(EmptyCart):
            TestOrder.objects.get_from_cart(cart)

    def test_order_is_updated_when_cart_content_changes(self):
        cart = TestCart.objects.create(typ='satchless.test_cart')
        cart.replace_item(self.macaw_blue, 1)

        order = order_app.order_model.objects.get_from_cart(cart)

        cart.replace_item(self.macaw_blue_fake, Decimal('2.45'))
        cart.replace_item(self.cockatoo_white_a, Decimal('2.45'))

        order_items = set()
        for group in order.groups.all():
            order_items.update(group.items.values_list('product_variant',
                                                       'quantity'))
        self.assertEqual(set(cart.items.values_list('variant', 'quantity')),
                         order_items)

    def test_str(self):
        order = TestOrder.objects.create(currency='USD')
        self.assertEqual(six.text_type(order), 'Order #%s' % order.pk)

    def test_billing_full_name(self):
        order = TestOrder(billing_first_name='Ada', billing_last_name='Lovelace')
        self.assertEqual(order.billing_full_name, 'Ada Lovelace')

    def test_set_status(self):
        order = TestOrder.objects.create(currency='USD')
        last_status_change = datetime.datetime.utcnow() - datetime.timedelta(hours=10)
        order.last_status_change = last_status_change
        order.save()
        with mock.patch.object(signals.order_status_changed, 'send'):
            order.set_status('fulfilled')
        self.assertEqual(order.status, 'fulfilled')
        self.assertTrue(order.last_status_change > last_status_change)

    def test_subtotal(self):
        cart = TestCart.objects.create(typ='satchless.test_cart')
        cart.replace_item(self.macaw_blue, 1)
        cart.replace_item(self.macaw_blue_fake, Decimal('2.45'))
        order = order_app.order_model.objects.get_from_cart(cart)
        self.assertEqual(order.subtotal(), Price(net=15, gross=15, currency='USD'))

    def test_payment_price(self):
        cart = TestCart.objects.create(typ='satchless.test_cart')
        cart.replace_item(self.macaw_blue, 1)
        cart.replace_item(self.macaw_blue_fake, Decimal('2.45'))
        order = order_app.order_model.objects.get_from_cart(cart)
        variant = PaymentVariant.objects.create(order=order, name='Gold-pressed latinum', price=10, amount=10)
        self.assertEqual(order.payment_price(), Price(net=10, gross=10, currency='USD'))

    def test_total(self):
        cart = TestCart.objects.create(typ='satchless.test_cart')
        cart.replace_item(self.macaw_blue, 1)
        cart.replace_item(self.macaw_blue_fake, Decimal('2.45'))
        order = order_app.order_model.objects.get_from_cart(cart)
        self.assertEqual(order.total(), Price(net=15, gross=15, currency='USD'))

    def test_no_paymentvariant(self):
        order = TestOrder.objects.create(currency='USD')
        self.assertIsNone(order.paymentvariant)

    def test_paymentvariant(self):
        order = TestOrder.objects.create(currency='USD')
        variant = PaymentVariant.objects.create(order=order, name='Gold-pressed latinum', price=10, amount=10)
        self.assertEqual(order.paymentvariant, variant)


class OrderedItemTest(TestCase):
    def setUp(self):
        order = TestOrder.objects.create(currency='USD')
        group = DeliveryGroup.objects.create(order=order)
        self.item = OrderedItem.objects.create(
            delivery_group=group,
            product_name='sherlock holmes holonovel',
            quantity=2,
            unit_price_net=Decimal('10'),
            unit_price_gross=Decimal('11'),
        )

    def test_unit_price(self):
        self.assertEqual(self.item.unit_price(), Price(net=10, gross=11, currency='USD'))

    def test_price(self):
        self.assertEqual(self.item.price(), Price(net=20, gross=22, currency='USD'))


class PaymentQueueTest(TestCase):
    def setUp(self):
        self.order = TestOrder.objects.create(currency='USD')
        self.customer = get_user_model().objects.create()

    def test_enum_types(self):
        self.assertEqual(
            list(payment_queue.enum_types(self.order, self.customer)),
            [
                (payment_queue.queue[0], TestPaymentType('gold', 'Gold', order=self.order, customer=self.customer)),
                (payment_queue.queue[0], TestPaymentType('silver', 'Silver', order=self.order, customer=self.customer)),
                (payment_queue.queue[1], TestPaymentType('platinum', 'Platinum', order=self.order, customer=self.customer)),
                (payment_queue.queue[1], TestPaymentType('gold-pressed-latinum', 'Gold-pressed latinum', order=self.order, customer=self.customer)),
            ]
        )

    def test_as_choices(self):
        self.assertEqual(
            payment_queue.as_choices(self.order, self.customer),
            [
                ('gold', 'Gold'),
                ('silver', 'Silver'),
                ('platinum', 'Platinum'),
                ('gold-pressed-latinum', 'Gold-pressed latinum'),
            ]
        )

    def test_get_configuration_form(self):
        data = {'foo': 'bar'}
        form = payment_queue.get_configuration_form(self.order, data, 'platinum')
        self.assertEqual(form.data, data)
        self.assertEqual(form.order, self.order)
        self.assertEqual(form.typ, 'platinum')

    def test_get_provider_not_configured(self):
        with self.assertRaises(ValueError):
            PaymentQueue()._get_provider(self.order, 'platinum')

    def test_get_configuration_forms(self):
        data = (
            ('gold', None),
            ('platinum', {'amount': 100}),
        )
        forms = payment_queue.get_configuration_forms(self.order, data)

        self.assertEqual(forms[0][0], 'gold')
        self.assertIsNone(forms[0][1])

        self.assertEqual(forms[1][0], 'platinum')
        self.assertEqual(forms[1][1].data, data[1][1])
        self.assertEqual(forms[1][1].order, self.order)
        self.assertEqual(forms[1][1].typ, 'platinum')

    def test_create_variant(self):
        data = {'amount': 100}
        form = payment_queue.get_configuration_form(self.order, data, typ='platinum')
        variant = payment_queue.create_variant(self.order, form, clear=False, typ='platinum')
        self.assertIsInstance(variant, PaymentVariant)
        self.assertEqual(variant.name, 'platinum')
        self.assertEqual(variant.order, self.order)
        self.assertEqual(variant.amount, 100)

        self.assertEqual(self.order.paymentvariant_set.all().count(), 1)

        variant = payment_queue.create_variant(self.order, form, clear=True, typ='platinum')
        self.assertIsInstance(variant, PaymentVariant)
        self.assertEqual(variant.name, 'platinum')
        self.assertEqual(variant.order, self.order)
        self.assertEqual(variant.amount, 100)

        self.assertEqual(self.order.paymentvariant_set.all().count(), 1)

    def test_create_variants(self):
        data = (
            ('gold', None),
            ('platinum', {'amount': 100}),
        )
        forms = payment_queue.get_configuration_forms(self.order, data)
        variants = payment_queue.create_variants(self.order, forms, clear=False)
        self.assertEqual(variants[0][0], 'gold')
        self.assertIsInstance(variants[0][1], PaymentVariant)
        self.assertEqual(variants[0][1].name, 'gold')
        self.assertEqual(variants[0][1].order, self.order)
        self.assertEqual(variants[0][1].amount, 0)

        self.assertEqual(variants[1][0], 'platinum')
        self.assertIsInstance(variants[1][1], PaymentVariant)
        self.assertEqual(variants[1][1].name, 'platinum')
        self.assertEqual(variants[1][1].order, self.order)
        self.assertEqual(variants[1][1].amount, 100)

        self.assertEqual(self.order.paymentvariant_set.all().count(), 2)

        variants = payment_queue.create_variants(self.order, forms, clear=True)
        self.assertEqual(variants[0][0], 'gold')
        self.assertIsInstance(variants[0][1], PaymentVariant)
        self.assertEqual(variants[0][1].name, 'gold')
        self.assertEqual(variants[0][1].order, self.order)
        self.assertEqual(variants[0][1].amount, 0)

        self.assertEqual(variants[1][0], 'platinum')
        self.assertIsInstance(variants[1][1], PaymentVariant)
        self.assertEqual(variants[1][1].name, 'platinum')
        self.assertEqual(variants[1][1].order, self.order)
        self.assertEqual(variants[1][1].amount, 100)

        self.assertEqual(self.order.paymentvariant_set.all().count(), 2)

    def test_confirms(self):
        data = (
            ('gold', None),
            ('platinum', {'amount': 100}),
        )
        forms = payment_queue.get_configuration_forms(self.order, data)
        variants = payment_queue.create_variants(self.order, forms, clear=False)
        payment_queue.confirms(self.order, variants)
        order = TestOrder.objects.get(id=self.order.pk)
        self.assertEqual(order.status, 'confirmed')

    def test_confirms_amount_error(self):
        data = (
            ('gold', None),
            ('platinum', {'amount': 100}),
        )
        forms = payment_queue.get_configuration_forms(self.order, data)
        variants = payment_queue.create_variants(self.order, forms, clear=False)
        variants[0][1].amount -= 1
        with self.assertRaises(PaymentFailure):
            payment_queue.confirms(self.order, variants)
