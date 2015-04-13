"""Grenier.
A wrapper around attic, rsync and duplicity.
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

#here = path.abspath(path.dirname(__file__))

setup(
    name='grenier',
    version='0.1.0',
    description='A wrapper around attic, rsync and duplicity.',
    #long_description=long_description,
    url='https://github.com/barsanuphe/grenier',
    author='barsanuphe',
    author_email='monadressepublique@gmail.com',
    license='GPLv3+',
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Operating System :: POSIX :: Linux',
        'Topic :: System :: Archiving :: Backup',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python :: 3.4',
    ],
    keywords='backup attic configuration wrapper',
    packages=['grenier'],

    # note: attic has unresolved dependancies (blosc) for now
    install_requires=['pyrax', 'pyyaml', 'notify2', 'crypto', 'xdg'],


    # If there are data files included in your packages that need to be
    # installed, specify them here.
    #package_data={
        #'sample': ['package_data.dat'],
    #},

    ## To provide executable scripts, use entry points in preference to the
    ## "scripts" keyword. Entry points provide cross-platform support and allow
    ## pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'grenier=grenier:main',
        ],
    },

)
