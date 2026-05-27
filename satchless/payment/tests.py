"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

import datetime
from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from django.test import TestCase

from ..order import models as order_models
from . import models
from . import PaymentProvider, PaymentType


class TestPaymentType(PaymentType):
    def __init__(self, typ, name, order=None, customer=None):
        super(TestPaymentType, self).__init__(typ, name)
        self.order = order
        self.customer = customer

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.typ == other.typ
            and self.name == other.name
            and self.order == other.order
            and self.customer == other.customer
        )

class TestPaymentProvider(PaymentProvider):
    def enum_types(self, order=None, customer=None):
        yield self, TestPaymentType('gold', 'Gold', order=order, customer=customer)
        yield self, TestPaymentType('silver', 'Silver', order=order, customer=customer)

    def create_variant(self, order, form, typ=None):
        return models.PaymentVariant.objects.create(
            order=order,
            name=typ,
            price=0,
            amount=0,
        )

    def confirm(self, order, typ=None, variant=None):
        order.set_status('confirmed')


class TestPaymentProvider2Form(forms.Form):
    amount = forms.IntegerField()

    def __init__(self, **kwargs):
        self.order = kwargs.pop('order')
        self.typ = kwargs.pop('typ')
        super(TestPaymentProvider2Form, self).__init__(**kwargs)


class TestPaymentProvider2(TestPaymentProvider):
    def enum_types(self, order=None, customer=None):
        yield self, TestPaymentType('platinum', 'Platinum', order=order, customer=customer)
        yield self, TestPaymentType('gold-pressed-latinum', 'Gold-pressed latinum', order=order, customer=customer)

    def get_configuration_form(self, order, data, typ=None):
        return TestPaymentProvider2Form(data=data, order=order, typ=typ)

    def create_variant(self, order, form, typ=None):
        if not form.is_valid():
            raise PaymentFailure(repr(form.errors))
        return models.PaymentVariant.objects.create(
            order=order,
            name=typ,
            price=Decimal(form.cleaned_data['amount']),
            amount=Decimal(form.cleaned_data['amount']),
        )


class PaymentProviderTest(TestCase):
    def setUp(self):
        self.p = TestPaymentProvider()
        self.order = order_models.Order.objects.create()
        self.customer = get_user_model().objects.create()

    def test_enum_types(self):
        self.assertEqual(
            list(self.p.enum_types(self.order, self.customer)),
            [
                (self.p, TestPaymentType('gold', 'Gold', order=self.order, customer=self.customer)),
                (self.p, TestPaymentType('silver', 'Silver', order=self.order, customer=self.customer)),
            ]
        )

    def test_as_choices(self):
        self.assertEqual(
            self.p.as_choices(self.order, self.customer),
            [
                ('gold', 'Gold'),
                ('silver', 'Silver'),
            ]
        )

    def test_get_configuration_form_default(self):
        self.assertEqual(
            self.p.get_configuration_form(self.order, None, 'gold'),
            None
        )

    def test_get_configuration_form_override(self):
        p = TestPaymentProvider2()
        data = {'amount': 100}
        form = p.get_configuration_form(self.order, data, 'platinum')
        self.assertIsInstance(form, TestPaymentProvider2Form)
        self.assertEqual(form.data, data)
        self.assertEqual(form.order, self.order)
        self.assertEqual(form.typ, 'platinum')


class PaymentVariantTest(TestCase):
    def test_str(self):
        self.assertEqual(str(models.PaymentVariant(name='platinum')), 'platinum')
