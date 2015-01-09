.. otplc documentation

###################
OTPLC Documentation
###################

A bidirectional brat_ standoff ↔︎ OTPL (one token per line) format converter for Python 3.
(Note that brat itself is based on Python 2.)

Why would you need this tool?
Many (most?) sequence taggers work with OTPL (one token per line) files to create text annotations;
For example, CRFSuite_, Factorie_, MALLET_, or Wapiti_.
But with brat one can create and manipulate visualizations of text annotations like no other tool.
brat can even show dependency relations and annotate semantic events between them.
Therefore, this tool helps to convert any OTPL corpus to and from the brat standoff format.
With OTPLC, it is possible to develop OTPL sequence taggers, and visually inspect, correct, and evaluate the annotations with brat.

.. _brat: http://brat.nlplab.org/index.html
.. _CRFSuite: http://www.chokkan.org/software/crfsuite/
.. _Factorie: http://factorie.cs.umass.edu/
.. _MALLET: http://mallet.cs.umass.edu/
.. _Wapiti: http://wapiti.limsi.fr/

.. toctree::
   :maxdepth: 2

``lst2ann.py``
==============

A command-line script for running the conversions.
To learn how to use the script, execute it with the ``--help`` option.

brat File Format
================

brat_: brat rapid annotation tool

Official suffix: ``.ann`` ("standoff annotations")

Encoding: UTF-8

Please refer to the official brat `standoff format`_ documentation for more information.

.. _standoff format: http://brat.nlplab.org/standoff.html

OTPL File Format
================

**OTPL**: One Token Per Line

Official suffix: ``.lst`` ("line-separated tokens")

Encoding: UTF-8

.. automodule:: otplc.colspec

``otplc`` API Documentation
===========================

.. automodule:: otplc

``otplc.colspec``
-----------------

Creating and working with column specifications.

.. autoclass:: otplc.colspec.ColumnSpecificationMetaClass
   :members:

.. autoclass:: otplc.colspec.ColumnSpecification
   :members:

``otplc.converter``
-------------------

.. automodule:: otplc.converter

.. autoclass:: otplc.converter.OtplBratConverter
   :members:

.. autofunction:: otplc.converter.otpl_to_brat

``otplc.reader``
----------------

.. automodule:: otplc.reader

.. autoclass:: otplc.reader.DataFormatError

.. autoclass:: otplc.reader.OtplReader
   :members:

.. autofunction:: otplc.reader.configure_reader

.. autofunction:: otplc.reader.guess_colspec

``otplc.settings``
------------------

.. automodule:: otplc.settings

.. autoclass:: otplc.settings.Configuration
   :members:
