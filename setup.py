from setuptools import setup

setup(
    name='PyUtils',
    version='1.2.1.dev1',
    package_dir={'': 'src'},
    packages=['Utils', 'PyQt5Utils', 'Transceiver'],
    url='https://github.com/GlebMorgan/PythonStuff',
    license='',
    author='GlebMorgan',
    author_email='glebmorgan@gmail.com',
    description='Utilities to use cross-project',
    package_data={
        'PyQt5Utils': ['res/*.py', 'res/refresh.gif']
    },
    install_requires=[
        'PyQt5', 'stdlib_list', 'orderedset', 'pySerial',
        'colorama', 'coloredlogs', 'verboselogs'
    ]
)
