
from django.test import TestCase

from ...product.tests import DeadParrot

from ..models import Category

__all__ = ['Models']

class Models(TestCase):

    def setUp(self):
        self.animals = Category.objects.create(slug='animals', name=u'Animals')
        self.birds = Category.objects.create(slug='birds', name=u'Birds',
                                             parent=self.animals)
        self.parrots = Category.objects.create(slug='parrots', name=u'Parrorts',
                                               parent=self.birds)

    def test_str(self):
        self.assertEqual(str(self.animals), u'Animals')
