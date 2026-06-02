#! /usr/bin/env python
import os
from setuptools import setup, find_packages

# CI publishes wheels with computed versions (pre-release dev tags off branch
# commits, real releases tagged from master). Honor the override so we don't
# need to commit a VERSION bump for every build.
version = os.environ.get('SATCHLESS_VERSION')
if not version:
    version_tuple = __import__('satchless').VERSION
    version = '.'.join([str(v) for v in version_tuple])

CLASSIFIERS = [
    'Development Status :: 3 - Alpha',
    'Environment :: Web Environment',
    'Framework :: Django',
    'Framework :: Django :: 2.2',
    'Framework :: Django :: 3.2',
    'Framework :: Django :: 4.2',
    'Framework :: Django :: 5.1',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: BSD License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
    'Programming Language :: Python :: 3.12',
    'Programming Language :: Python :: 3.13',
    'Programming Language :: Python :: 3.14',
    'Topic :: Internet :: WWW/HTTP',
    'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    'Topic :: Software Development :: Libraries :: Application Frameworks',
    'Topic :: Software Development :: Libraries :: Python Modules',
]

REQUIREMENTS = [
    'Django>=2.2',
    'django-mptt>=0.13.0',
]

EXTRAS = {
    'authorize.net payment provider': [
        'django-authorizenet >= 1.0'
    ],
    'django-payments payment provider': [
        'django-payments'
    ],
    'mamona payment provider': [
        'mamona',
    ],
    'stripe payment provider': [
        'stripe',
    ],
}

setup(name='satchless',
      author='Mirumee Software',
      author_email='hello@mirumee.com',
      description='An e-commerence framework for Django',
      license='BSD',
      version=version,
      url='http://satchless.com/',
      packages=find_packages(exclude=['doc*', 'examples*', 'tests*',
                                      'website*']),
      include_package_data=True,
      classifiers=CLASSIFIERS,
      install_requires=REQUIREMENTS,
      extras_require=EXTRAS,
      python_requires='>=3.10',
      platforms=['any'],
      zip_safe=False)
