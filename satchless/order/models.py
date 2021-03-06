from __future__ import absolute_import
import datetime
import decimal
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils.translation import ugettext_lazy as _
import random

from ..pricing import Price
from ..product.models import Variant
from ..util import countries
from . import signals
from .exceptions import EmptyCart
import six
from six.moves import range

class OrderManager(models.Manager):

    def get_from_cart(self, cart, instance=None):
        '''
        Create an order from the user's cart, possibly discarding any previous
        orders created for this cart.
        '''
        from .handler import partitioner_queue
        if cart.is_empty():
            raise EmptyCart("Cannot create empty order.")
        previous_orders = self.filter(cart=cart)
        if not instance:
            order = self.model.objects.create(cart=cart, user=cart.owner,
                                              currency=cart.currency)
        else:
            order = instance
            for group in order.groups.all():
                group.items.all().delete()
                group.delete()
            order.paymentvariant_set.all().delete()
        groups = partitioner_queue.partition(cart)
        for group in groups:
            delivery_group = order.create_delivery_group()
            for item in group:
                ordered_item = order.create_ordered_item(delivery_group, item)
                ordered_item.save()

        previous_orders = (previous_orders.exclude(pk=order.pk)
                                          .filter(status='checkout'))
        previous_orders.delete()
        return order

class Order(models.Model):
    STATUS_CHOICES = (
        ('checkout', _('undergoing checkout')),
        ('payment-pending', _('waiting for payment')),
        ('payment-complete', _('paid')),
        ('payment-failed', _('payment failed')),
        ('delivery', _('shipped')),
        ('cancelled', _('cancelled')),
    )
    # Do not set the status manually, use .set_status() instead.
    status = models.CharField(_('order status'), max_length=32,
                              choices=STATUS_CHOICES, default='checkout')
    created = models.DateTimeField(default=datetime.datetime.now,
                                   editable=False, blank=True)
    last_status_change = models.DateTimeField(default=datetime.datetime.now,
                                   editable=False, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True,
                             related_name='orders',
                             on_delete=models.PROTECT)
    currency = models.CharField(max_length=3)
    billing_first_name = models.CharField(_("first name"),
                                          max_length=256, blank=True)
    billing_last_name = models.CharField(_("last name"),
                                         max_length=256, blank=True)
    billing_company_name = models.CharField(_("company name"),
                                            max_length=256, blank=True)
    billing_street_address_1 = models.CharField(_("street address 1"),
                                                max_length=256, blank=True)
    billing_street_address_2 = models.CharField(_("street address 2"),
                                                max_length=256, blank=True)
    billing_city = models.CharField(_("city"), max_length=256, blank=True)
    billing_postal_code = models.CharField(_("postal code"),
                                           max_length=20, blank=True)
    billing_country = models.CharField(_("country"),
                                       choices=countries.COUNTRY_CHOICES,
                                       max_length=2, blank=True)
    billing_country_area = models.CharField(_("country administrative area"),
                                            max_length=128, blank=True)
    billing_tax_id = models.CharField(_("tax ID"), max_length=40, blank=True)
    billing_phone = models.CharField(_("phone number"),
                                     max_length=30, blank=True)
    payment_type = models.CharField(max_length=256, blank=True)
    token = models.CharField(max_length=32, blank=True, default='')

    class Meta:
        # Use described string to resolve ambiguity of the word 'order' in English.
        verbose_name = _('order (business)')
        verbose_name_plural = _('orders (business)')
        ordering = ('-last_status_change',)

    def __str__(self):
        return _('Order #%d') % self.id

    def save(self, *args, **kwargs):
        if not self.token:
            for i in range(100):
                token = ''.join(random.sample(
                                '0123456789abcdefghijklmnopqrstuvwxyz', 32))
                if not Order.objects.filter(token=token).exists():
                    self.token = token
                    break
        return super(Order, self).save(*args, **kwargs)

    @property
    def billing_full_name(self):
        return u'%s %s' % (self.billing_first_name, self.billing_last_name)

    def set_status(self, new_status, extra_fields=[]):
        old_status = self.status
        self.status = new_status
        self.last_status_change = datetime.datetime.now()
        self.save(update_fields=['status', 'last_status_change']+extra_fields)
        signals.order_status_changed.send(sender=type(self), instance=self,
                                          old_status=old_status)

    def subtotal(self):
        return sum([g.subtotal(currency=self.currency) for g in self.groups.all()],
                   Price(0, currency=self.currency))

    def payment_price(self):
        return Price(
            sum([p.price for p in self.paymentvariant_set.all()], 0),
            currency=self.currency
        )

    def total(self):
        payment_price = self.payment_price()
        return payment_price + sum([g.total() for g in self.groups.all()],
                                   Price(0, currency=self.currency))

    def create_delivery_group(self):
        return self.groups.create(order=self)

    def create_ordered_item(self, delivery_group, item):
        price = item.get_unit_price()
        variant = item.variant.get_subtype_instance()
        name = six.text_type(variant)
        ordered_item_class = self.get_ordered_item_class()
        ordered_item = ordered_item_class(delivery_group=delivery_group,
                                          product_variant=item.variant,
                                          product_name=name,
                                          quantity=item.quantity,
                                          unit_price_net=price.net,
                                          unit_price_gross=price.gross)
        return ordered_item

    def get_ordered_item_class(self):
        return OrderedItem

    @property
    def paymentvariant(self):
        try:
            return self.paymentvariant_set.all()[0]
        except IndexError:
            return None


class DeliveryGroup(models.Model):
    order = models.ForeignKey(Order, related_name='groups', on_delete=models.PROTECT)
    delivery_type = models.CharField(max_length=256, blank=True)

    def subtotal(self, currency=None):
        currency = currency or self.order.currency
        return sum([i.price(currency=currency) for i in self.items.all()],
                Price(0, currency=currency))

    def total(self):
        return sum([i.price() for i in self.items.all()],
                                    Price(0, currency=self.order.currency))


class OrderedItem(models.Model):
    delivery_group = models.ForeignKey(DeliveryGroup, related_name='items', on_delete=models.PROTECT)
    product_variant = models.ForeignKey(Variant, blank=True, null=True,
                                        related_name='+',
                                        on_delete=models.PROTECT)
    product_name = models.CharField(max_length=128)
    quantity = models.DecimalField(_('quantity'),
                                   max_digits=10, decimal_places=4)
    unit_price_net = models.DecimalField(_('unit price (net)'),
                                         max_digits=12, decimal_places=4)
    unit_price_gross = models.DecimalField(_('unit price (gross)'),
                                           max_digits=12, decimal_places=4)

    def unit_price(self):
        return Price(net=self.unit_price_net, gross=self.unit_price_gross,
                     currency=self.delivery_group.order.currency)

    def price(self, currency=None):
        net = self.unit_price_net * self.quantity
        gross = self.unit_price_gross * self.quantity
        currency = currency or self.delivery_group.order.currency
        return Price(net=net.quantize(decimal.Decimal('0.01')),
                 gross=gross.quantize(decimal.Decimal('0.01')),
                 currency=currency)
