# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Sotiris.
#
# invenio-maDMP is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Invenio modules that handles maDMPs"""

from __future__ import absolute_import, print_function

from .ext import inveniomaDMP
from .version import __version__

__all__ = ('__version__', 'inveniomaDMP')
