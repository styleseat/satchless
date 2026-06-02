from django import forms
from django.db import models

from ..models import ProductAbstract, Variant

#models for tests

class DeadParrot(ProductAbstract):
    species = models.CharField(max_length=20)


class ZombieParrot(DeadParrot):
    pass


class DeadParrotVariant(Variant):
    COLOR_CHOICES = (
        ('blue', 'blue'),
        ('white', 'white'),
        ('red', 'red'),
        ('green', 'green'),
    )
    product = models.ForeignKey(DeadParrot, related_name='variants', on_delete=models.PROTECT)
    color = models.CharField(max_length=10, choices=COLOR_CHOICES)
    looks_alive = models.BooleanField(default=False)

    class Meta:
        unique_together = ('product', 'color', 'looks_alive')

    def __str__(self):
        "For debugging purposes"
        return u"%s %s %s" % (
                "alive" if self.looks_alive else "resting",
                self.get_color_display(), self.product.slug)


from .product import *
from .pricing import *
