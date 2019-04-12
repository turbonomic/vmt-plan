.. # Links
.. _CPython: http://www.python.org/
.. _PyPi: http://pypi.org/
.. _Requests: http://docs.python-requests.org/en/master/
.. _IronPython: http://http://ironpython.net/
.. _repository: https://github.com/rastern/vmt-plan
.. _releases: https://github.com/rastern/vmt-plan/releases
.. _vmt-connect: https://github.com/rastern/vmt-connect/
.. _enum34: https://pypi.python.org/pypi/enum34
.. _aenum: https://pypi.python.org/pypi/aenum/2.0.8

============
Installation
============

Prior to version 2.0, *vmt-plan* was distributed as a stand-alone single file
Python module, which could be placed into the same folder as the calling script.
As of version 2.0, *vmt-plan* is now distributed as a Python wheel package to be
installed via pip. The package is not available on PyPi_ at this time.

.. code:: bash

   pip install vmtplan-2.0.0-py3-none-any.whl


Requirements
============

In order to use *vmt-plan* you will need to be running a supported version of
Python, and install the vmt-connect_ module.

* Python:

  - CPython_ >= 3.4

* Enum -- one of the following:

  - CPython >= 3.4 (for native Enum support)
  - enum34_ >= 1.1.6
  - aenum_ >= 2.0.6

* vmt-connect_ >= 3.0.0


Importing
=========

In the most basic case, you need to import the package.

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
=============

The source code for *vmt-plan* is provided via a read-only GitHub repository_.

Individual release archives may be found `here`__.

__ releases_