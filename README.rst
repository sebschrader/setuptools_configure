####################
setuptools_configure
####################

:code:`setuptools_configure` adds a configure step to setuptools-based projects,
that allows you to define variables that can be substituted in the distribution
metadata or any project file.

Every major build system like :code:`autotools`, :code:`cmake` or :code:`scons`,
includes facilities to configure builds.

Basic Usage
===========

..code:: python
    from setuptools_configure import setup

    setup(name='my-project',
          version='1.0',
          substitutions={
              '': '',
          },
          )

Predefined Variables
====================

:code:`setuptools_configure` already predefines the following variables for you.
You may overwrite these variables.

:code:`PACKAGE_NAME`
   The value given to the :code:`name` keyword argument of the  :code:`setup`
   function.

:code:`PACKAGE_VERSION`, :code:`PACKAGE_AUTHOR`, :code:`PACKAGE_AUTHOR_EMAIL`, :code:`PACKAGE_URL`
   Like :code:`PACKAGE_NAME`.

Configuring Files
=================

Exporting to Python
===================

Most of the time, you want to be able to access the build configuration during
the runtime of your code.
You could write a template, e.g :code:`constants.py.in` and declare it in
:code:`configure_files`.
However, this is tedious and error-prone, as you have to

You can declare :code:`constants_module` which contains all substitution
variables and their values and which will be generated automatically
by :code:`setuptools_configure` during the :code:`configure` step.

Dynamic Variables
=================

Caching
=======

Limitations
===========

Most setuptools extensions can be used without importing them directly in the
:code:`setup.py` file.

Either they are just installed and their commands and keywords are available
through :code:`pkg_resources` entry point mechanism or they can be depended on
explicitly with the :code:`setup_requires` keyword argument of the :code:`setup`
function.

:code:`setuptools_configure` however can not work this way, due to the
implementation of :code:`distutils` and :code:`setuptools`.

A custom :code:`setup` function is necessary, that is executed before
:code:`setuptools` does anything. This means that you have to have
:code:`setuptools_configure` installed before you can run :code:`setup.py`.

Changelog
=========

0.1.0 (2016-07-28)
------------------
* Initial release
