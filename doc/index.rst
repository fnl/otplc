.. otplc documentation

###################
OTPLC Documentation
###################

A bidirectional brat_ ↔︎ OTPL format converter
(in slowly but surely out-dated Python **2** only, just as brat itself).

Why would you need this tool?
Many sequence taggers work with OTPL files; for example, CRFSuite_, Factorie_, MALLET_, or Wapiti_.
But no other tool can create as stunning visualizations of text annotations, including relations
and events between them, as brat_ does.
Therefore, it would be great if any corpora could be converted to and from those format to be able
to use them to train a sequence tagger.
Furthermore, it would be great to go back into brat to visually inspect the results of the tagger
on unseen data.
This scenario is exactly what this Python 2 package solves.

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
