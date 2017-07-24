.. # Links
.. _CPython: http://www.python.org/
.. _PyPy: http://pypy.org/
.. _Requests: http://docs.python-requests.org/en/master/
.. _IronPython: http://http://ironpython.net/
.. _repository: https://github.com/rastern/vmt-plan
.. _releases: https://github.com/rastern/vmt-plan/releases
.. _vmt-connect: https://github.com/rastern/vmt-connect/
.. _enum34: https://pypi.python.org/pypi/enum34
.. _aenum: https://pypi.python.org/pypi/aenum/2.0.8

Installation
============

vmt-plan is a stand-alone Python module, and not provided as a PyPi package.
The module can be placed in the same folder as your calling script and imported
locally, or it can be placed in a folder included in the ``PYTHONPATH``.


Requirements
-------------

In order to use vmt-plan you will need to be running a supported version of
Python, and install the Requests_ module.

* Python -- one of the following:

  - CPython_ >= 2.7 or >= 3.3

* Enum -- one of the following:

  - CPython >= 3.4 (for native Enum support)
  - enum34_ >= 1.1.6
  - aenum_ >= 2.0.6

* vmt-connect_ >= 1.1.0


Importing
---------

In the most basic case, you need to import the module, either from a local source
file or from a location in your ``PYTHONPATH``.

.. code:: python

   import vmtplanner

However, you may find it more useful to alias the import

.. code:: python

   import vmtplanner as vp

Alternatively, you can manually update the internal import search path within
your script to import vmt-connect from another location. For instance, if you
created a folder in your project directory for local modules called `modules`,
you could add the relative path for importing:

.. code:: python

   import os
   import sys
   sys.path.insert(0, os.path.abspath('./modules'))

   import vmtplanner


GitHub Source
-------------

The source code for vmt-plan is provided via a read-only GitHub repository_.

Individual release archives may be found `here`__.

__ releases_