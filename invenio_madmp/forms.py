# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Sotirios Tsepelakis.
#
# invenio-maDMP is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.

"""maDMP deposit form module."""

from __future__ import absolute_import, print_function

from datetime import datetime

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired

from wtforms import SelectField, StringField, validators, \
    FieldList, RadioField, ValidationError, FormField, TextAreaField
from wtforms.fields.html5 import DateField

from .api import UploadMaDMP


class ContributorForm(FlaskForm):
    """Contributor Form"""

    name = StringField([validators.DataRequired()], render_kw={"placeholder": "name"})
    role = StringField([validators.DataRequired()], render_kw={"placeholder": "role"})
    mail = StringField(render_kw={"placeholder": "email"})


class MaDMPForm(FlaskForm):
    """maDMP deposit form."""

    file = FileField('Insert your file here', validators=[FileRequired()])
    upload_type = SelectField('Upload Type', [validators.DataRequired()],
                              default='Dataset',
                              choices=[
                                  ('AudioVisual', 'Audio Visual'),
                                  ('Collection', 'Collection'),
                                  ('DataPaper', 'Data Paper'),
                                  ('Dataset', 'Dataset'),
                                  ('Event', 'Event'),
                                  ('Image', 'Image'),
                                  ('InteractiveResource', 'Interactive Resource'),
                                  ('Model', 'Model'),
                                  ('PhysicalObject', 'Physical Object'),
                                  ('Service', 'Service'),
                                  ('Software', 'Software'),
                                  ('Sound', 'Sound'),
                                  ('Text', 'Text'),
                                  ('Workflow', 'Workflow'),
                                  ('Other', 'Other')
                              ]
                              )

    publication_date = DateField('Publication Date', [validators.DataRequired()],
                                 default=datetime.today
                                 )
    title = StringField('Title', [validators.DataRequired()])

    contributors = StringField('Contributors', [validators.DataRequired()])

    description = TextAreaField('Description')
    keywords = StringField('Keywords')

    ethical_issues = RadioField('Ethical Issues', [validators.DataRequired()],
                                default='unknown',
                                choices=[
                                    ('yes', 'Yes'),
                                    ('no', 'No'),
                                    ('unknown', 'Unknown')
                                ])
    access_right = RadioField('Access Right:', [validators.DataRequired()],
                              default='open',
                              choices=[
                                  ('open', 'Open Access'),
                                  ('embargo', 'Embargoed Access'),
                                  ('restricted', 'Restricted Access'),
                                  ('closed', 'Closed Access')
                              ])
    personal_data = RadioField('Personal data', [validators.DataRequired()],
                               default='unknown',
                               choices=[
                                   ('yes', 'Yes'),
                                   ('no', 'No'),
                                   ('unknown', 'Unknown')
                               ])
    sensitive_data = RadioField('Sensitive data', [validators.DataRequired()],
                                default='unknown',
                                choices=[
                                    ('yes', 'Yes'),
                                    ('no', 'No'),
                                    ('unknown', 'Unknown')
                                ])

    license_ref = StringField('License Reference', [validators.DataRequired(), validators.URL()])

    @staticmethod
    def validate_license_ref(form, field):
        if not UploadMaDMP.validate_license(field.data):
            raise ValidationError('Incorrect License')


class FileForm(FlaskForm):
    file = FileField('Insert your file here', validators=[FileRequired()])
