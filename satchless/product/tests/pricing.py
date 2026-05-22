import decimal
from django.conf import settings
from django.test import TestCase
from django import template
import mock
from satchless.pricing import Price, PriceRange, PricingHandler
from satchless.pricing.handler import PricingQueue

__all__ = ['BasicHandlerTest']

class FiveZlotyPriceHandler(PricingHandler):
    """Dummy base price handler - everything has 5USD price"""

    def get_variant_price(self, *args, **kwargs):
        return Price(net=5, gross=5, currency=u'USD')

    def get_product_price_range(self, *args, **kwargs):
        return PriceRange(min_price=Price(net=5, gross=5, currency=u'USD'),
                          max_price=Price(net=5, gross=5, currency=u'USD'))

class NinetyPerecentTaxPriceHandler(PricingHandler):
    """Scary price handler - it counts 90% of tax for everything"""

    def _tax(self, price):
        return Price(currency=price.currency, net=price.net,
                     gross=price.gross*decimal.Decimal('1.9'))

    def get_variant_price(self, *args, **kwargs):
        price = kwargs.get('price')
        return self._tax(price)

    def get_product_price_range(self, *args, **kwargs):
        price_range = kwargs.get('price_range')
        return PriceRange(min_price=self._tax(price_range.min_price),
                          max_price=self._tax(price_range.max_price))

class TenPercentDiscountPriceHandler(PricingHandler):
    """Discount all handler"""

    def _discount(self, price):
        return Price(currency=price.currency,
                     net=price.net*decimal.Decimal('0.9'),
                     gross=price.gross*decimal.Decimal('0.9'))

    def get_variant_price(self, *args, **kwargs):
        price = kwargs.pop('price')
        if kwargs.get('discount', True):
            return self._discount(price)
        return price

    def get_product_price_range(self, *args, **kwargs):
        price_range = kwargs.pop('price_range')
        if kwargs.get('discount', True):
            return PriceRange(min_price=self._discount(price_range.min_price),
                              max_price=self._discount(price_range.max_price))
        return price_range

class BasicHandlerTest(TestCase):
    def setUp(self):
        self.pricing_queue = PricingQueue(FiveZlotyPriceHandler,
                                        NinetyPerecentTaxPriceHandler,
                                        TenPercentDiscountPriceHandler)

    def tearDown(self):
        self.pricing_queue = PricingQueue(*settings.SATCHLESS_PRICING_HANDLERS)

    def test_discounted_price(self):
        price = self.pricing_queue.get_variant_price(None, u'USD', quantity=1,
                                          discount=True)
        self.assertEqual(price,
                         Price(net=5*decimal.Decimal('0.9'),
                               gross=(5 * decimal.Decimal('1.9') *
                                      decimal.Decimal('0.9')),
                               currency=u'USD'))

    def test_undiscounted_price(self):
        price = self.pricing_queue.get_variant_price(None, u'USD', quantity=1,
                                          discount=False)
        self.assertEqual(price,
                         Price(net=5,
                               gross=5*decimal.Decimal('1.9'),
                               currency=u'USD'))
