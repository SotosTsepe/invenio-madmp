# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Sotiris.
#
# invenio-maDMP is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Module tests."""

from __future__ import absolute_import, print_function

from flask import Flask

from invenio_madmp import inveniomaDMP


def test_version():
    """Test version import."""
    from invenio_madmp import __version__
    assert __version__


def test_init():
    """Test extension initialization."""
    app = Flask('testapp')
    ext = inveniomaDMP(app)
    assert 'invenio-madmp' in app.extensions

    app = Flask('testapp')
    ext = inveniomaDMP()
    assert 'invenio-madmp' not in app.extensions
    ext.init_app(app)
    assert 'invenio-madmp' in app.extensions


def test_view(base_client):
    """Test view."""
    res = base_client.get("/")
    assert res.status_code == 200
    assert 'Welcome to invenio-maDMP' in str(res.data)
