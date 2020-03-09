..
    Copyright (C) 2020 Sotirios Tsepelakis.

    invenio-maDMP is free software; you can redistribute it and/or modify
    it under the terms of the MIT License; see LICENSE file for more details.

============
Installation
============

invenio-maDMP is on PyPI so all you need is:

.. code-block:: console

   $ pip install invenio-madmp


.. note::
 | You will also need to replace manually (for now) the json_ and elasticsearch_ schemas which come with Invenio,
 | as well as the `marshmallow json.py`_ file.
 |
 | Last but not least you will have to overwrite the record.html file in order to be able to attach files and
 | export their metadata.

.. _json:
.. _elasticsearch:
.. _marshmallow json.py:
