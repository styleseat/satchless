from django.db import models
from django.dispatch import receiver


class Subtyped(models.Model):
    subtype_attr = models.CharField(max_length=500, editable=False)
    __in_unicode = False

    class Meta:
        abstract = True

    def get_subtype_instance(self):
        """
        Caches and returns the final subtype instance. If refresh is set,
        the instance is taken from database, no matter if cached copy
        exists.
        """
        subtype = self
        path = self.subtype_attr.split()
        whoami = self._meta.model_name
        remaining = path[path.index(whoami)+1:]
        for r in remaining:
            subtype = getattr(subtype, r)
        return subtype

    def store_subtype(self, klass):
        if not self.id:
            path = [self]
            parents = list(self._meta.parents.keys())
            while parents:
                parent = parents[0]
                path.append(parent)
                parents = list(parent._meta.parents.keys())
            path = [p._meta.model_name for p in reversed(path)]
            self.subtype_attr = ' '.join(path)


@receiver(models.signals.pre_save)
def _store_content_type(sender, instance, **kwargs):
    if isinstance(instance, Subtyped):
        instance.store_subtype(instance)
