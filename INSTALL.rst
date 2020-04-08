..
    Copyright (C) 2020 Sotirios Tsepelakis.

    invenio-maDMP is free software; you can redistribute it and/or modify
    it under the terms of the MIT License; see LICENSE file for more details.

============
Installation
============

You can simply install invenio-maDMP by running:

.. code-block:: console

   $ pip install git+https://github.com/SotosTsepe/invenio-madmp


.. note::
   You will also need to replace manually (for now) the json_ and elasticsearch_ schemas which come with Invenio,
   as well as the `marshmallow json.py`_ file.

   Last but not least you will have to overwrite the `record.html`_ file in order to be able to attach files and
   export their metadata.

.. _json: https://github.com/SotosTsepe/invenio-madmp/blob/master/files/json/record-v1.0.0.json
.. _elasticsearch: https://github.com/SotosTsepe/invenio-madmp/blob/master/files/elasticsearch/record-v1.0.0.json
.. _marshmallow json.py: https://github.com/SotosTsepe/invenio-madmp/blob/master/files/marshmallow/json.py
.. _record.html: https://github.com/SotosTsepe/invenio-madmp/blob/master/files/record.html
