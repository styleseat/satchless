# -*- coding: utf-8 -*-
import os

from django.conf import settings
from django.test import TestCase, Client

from ..models import Variant, Product

from . import DeadParrot, DeadParrotVariant, ZombieParrot

__all__ = ['ModelsTest']


class ModelsTest(TestCase):
    def setUp(self):
        settings.DEBUG = True
        self.macaw = DeadParrot.objects.create(slug='macaw',
                species='Hyacinth Macaw')
        self.cockatoo = DeadParrot.objects.create(slug='cockatoo',
                species='White Cockatoo')
        self.client_test = Client()

    def test_product_subclass_promotion(self):
        for product in Product.objects.all():
            # test saving as base and promoted class
            self.assertEqual(type(product.get_subtype_instance()), DeadParrot)
            Product.objects.get(pk=product.pk).save()
            self.assertEqual(type(product.get_subtype_instance()), DeadParrot)
            DeadParrot.objects.get(pk=product.pk).save()
            self.assertEqual(type(product.get_subtype_instance()), DeadParrot)
            self.assertEqual(str(product), product.slug)

    def test_variants(self):
        self.macaw.variants.create(color='blue', looks_alive=False)
        self.macaw.variants.create(color='blue', looks_alive=True)
        self.assertEqual(2, self.macaw.variants.count())

        self.cockatoo.variants.create(color='white', looks_alive=True)
        self.cockatoo.variants.create(color='white', looks_alive=False)
        self.cockatoo.variants.create(color='blue', looks_alive=True)
        self.cockatoo.variants.create(color='blue', looks_alive=False)
        self.assertEqual(4, self.cockatoo.variants.count())

        for variant in Variant.objects.all():
            # test saving as base and promoted class
            self.assertEqual(type(variant.get_subtype_instance()), DeadParrotVariant)
            Variant.objects.get(pk=variant.pk).save()
            self.assertEqual(type(variant.get_subtype_instance()), DeadParrotVariant)
            DeadParrotVariant.objects.get(pk=variant.pk).save()
            self.assertEqual(type(variant.get_subtype_instance()), DeadParrotVariant)
