"""Grenier.
A wrapper around bup, encfs, rsync, and rclone.
"""

from setuptools import setup

setup(
    name='grenier',
    version='0.2.0',
    description='A wrapper around bup, rsync, rclone and encfs.',
    # long_description=long_description,
    url='https://github.com/barsanuphe/grenier',
    author='barsanuphe',
    author_email='mon.adresse.publique@gmail.com',
    license='GPLv3+',
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 2 - Pre-Alpha'
        'Intended Audience :: Developers',
        'Operating System :: POSIX :: Linux',
        'Topic :: System :: Archiving :: Backup',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python :: 3.5',
    ],
    keywords='backup bup configuration wrapper',
    packages=['grenier'],

    install_requires=['pyyaml', 'notify2', 'progressbar', 'pyxdg', 'pexpect'],


    # If there are data files included in your packages that need to be
    # installed, specify them here.
    # package_data={
    # 'sample': ['package_data.dat'],
    # },

    # main
    entry_points={
        'console_scripts': [
            'grenier=grenier:main',
        ],
    },
)
