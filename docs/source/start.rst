.. # Links
.. _CPython: http://www.python.org/
.. _PyPi: http://pypi.org/
.. _Requests: http://docs.python-requests.org/en/master/
.. _IronPython: http://http://ironpython.net/
.. _repository: https://github.com/turbonomic/vmt-plan
.. _releases: https://github.com/turbonomic/vmt-plan/releases
.. _vmt-connect: https://github.com/turbonomic/vmt-connect/
.. _enum34: https://pypi.python.org/pypi/enum34
.. _aenum: https://pypi.python.org/pypi/aenum/2.0.8
.. _Apache 2.0: https://github.com/turbonomic/vmt-plan/blob/master/LICENSE
.. _Turbonomic: http://www.turbonomic.com
.. _umsg: https://umsg.readthedocs.io/

===============
Getting Started
===============

About
=====

*vmt-plan* is a companion library to `vmt-connect`_ for working with the `Turbonomic`_
API. The core purpose of the library is to provide interfaces for constructing
and running plans within Turbonomic.


Installation
============

.. code:: bash

   pip install vmtplan


Requirements
------------

In order to use *vmt-plan* you will need to be running a supported version of
Python, and install the vmt-connect_ module.

* Python:

  - CPython_ >= 3.6

* vmt-connect_ >= 3.4.1
* umsg_ >= 1.0.2


Importing
---------

In the most basic case, you need to import the package. Note the package import
name "vmtplanner" differs from the Pypi package name "vmtplan".

.. code:: python

   import vmtplanner

However, you may find it more useful to alias the import

.. code:: python

   import vmtplanner as vp


GitHub Source
=============

The source code for *vmt-plan* is provided via a read-only GitHub repository_.

Individual release archives may be found `here`__.

__ releases_


Contributors
============

Creator and Principal Author:
  * R.A. Stern

Contributors:
  * Austin Portal
  * Chris Sawtelle
  * Ray Mileo
  * Ryan Geyer


License
=======

*vmt-plan* is distributed under the `Apache 2.0`_ software license, which may
also be obtained from the Apache Software Foundation, http://www.apache.org/licenses/LICENSE-2.0
