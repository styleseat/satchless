from django.db import models
from django.utils.translation import gettext_lazy as _
from mptt.models import MPTTModel

from ..product.models import Product

__all__ = ('Category', )


class Category(MPTTModel):
    name = models.CharField(_('name'), max_length=128)
    description = models.TextField(_('description'), blank=True)
    meta_description = models.TextField(_('meta description'), blank=True,
            help_text=_("Description used by search and indexing engines"))
    slug = models.SlugField(max_length=50)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT,
                               related_name='children')
    products = models.ManyToManyField(Product, related_name='categories',
                                      blank=True)

    class Meta:
        verbose_name = _("category")
        verbose_name_plural = _("categories")

    def __str__(self):
        return self.name
