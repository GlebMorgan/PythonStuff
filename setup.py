from setuptools import setup

setup(
    name='PyUtils',
    version='1.1dev2.3',
    package_dir = {'': 'src'},
    packages=['Utils', 'PyQt5Utils', 'Transceiver'],
    url='https://github.com/GlebMorgan/PythonStuff',
    license='',
    author='GlebMorgan',
    author_email='glebmorgan@gmail.com',
    description='Utilities to use cross-project',
    install_requires=['PyQt5', 'stdlib_list', 'orderedset', 'pySerial']
)
