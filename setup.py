from setuptools import setup

with open('README.rst') as fp:
    long_description = fp.read()

setup(name='setuptools_configure',
      version='0.1.0',
      author='Sebastian Schrader',
      author_email='sebastian.schrader@ossmail.de',
      url='http://github.com/sebschrader/setuptools_configure',
      description='Add a configure step to setuptools projects',
      long_description=long_description,
      license='MIT',
      packages=['setuptools_configure'],
      entry_points={
            'distutils.setup_keywords': [
                  'configure_files = '
                  'setuptools_configure:validate_configure_files',
                  'constants_module = '
                  'setuptools_configure:validate_constants_module',
                  'substitutions = setuptools_configure:validate_substitutions',
            ],
            'distutils.commands': [
                  'configure = setuptools_configure:configure',
            ],
      },
      classifiers=[
            'Development Status :: 4 - Beta',
            'License :: OSI Approved :: MIT License',
            'Intended Audience :: Developers',
            'Programming Language :: Python :: 3 :: Only',
            'Programming Language :: Python :: 3.3',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Topic :: Software Development :: Libraries',
            'Topic :: System :: Software Distribution',
            'Topic :: Utilities',
      ],
      )
