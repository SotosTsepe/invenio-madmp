# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Sotirios Tsepelakis.
#
# invenio-maDMP is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.

"""Views for deposit of records."""

from __future__ import absolute_import, print_function

import json
import os

from flask import Blueprint, abort, current_app, flash, \
    make_response, redirect, render_template, request, url_for
from flask_login import login_required
from flask_security import current_user
from invenio_db import db
from sqlalchemy import text
from werkzeug.utils import secure_filename

from invenio_madmp.api import UploadMaDMP, get_license_mapping
from invenio_madmp.forms import MaDMPForm, FileForm

# define a new Flask Blueprint that is registered under the url path /madmp
blueprint = Blueprint(
    'maDMP',
    __name__,
    url_prefix='/madmp',
    template_folder='templates',
    static_folder='static',
)


class Error:
    """Error template builder."""

    def __init__(self, status: int, err_type: str):
        """Error constructor."""
        self.status = status

        if status == 400:
            self.err_type = err_type

    def make_error(self):
        """Checks status code and builds the corresponding error."""
        if self.status // 10**2 % 10 == 4:  # client errors

            if self.status == 400:

                @blueprint.errorhandler(self.status)
                def bad_request():
                    if self.err_type == 'Invalid Format':
                        return make_response(render_template('invenio_madmp/errors/400_wrong_format.html'), self.status)
                    elif self.err_type == 'Foo':  # future use case
                        return make_response(render_template('foobar.html'), self.status)

                return bad_request()

        elif self.status // 10 % 10 == 5:

            @blueprint.errorhandler(self.status)
            def server_error():  # server errors
                pass


def valid_formats():
    """
    Defines valid formats for export.

    :returns: Tuple with valid formats
    """
    return ('json',)


def query_db(query, **kwargs):
    """
    Make a query to the Invenio DB.

    :param query: Query to run
    :returns: Result of the query as list
    """
    instance = db.session.execute(text(query), kwargs)
    result = [{column: value for column, value in rowproxy.items()} for rowproxy in instance]
    result = result.pop(0)
    return result


@blueprint.route('/upload', methods=('GET', 'POST'))
@login_required
def create():
    """
    Renders the upload form and saves the file and its metadata respectively.

    :returns: The success endpoint if upload was successful, self with errors otherwise
    """
    form = MaDMPForm()

    # if the form is submitted and validated
    if form.validate_on_submit():
        files_dir = os.path.join(current_app.instance_path, 'data')
        os.makedirs(files_dir, exist_ok=True)

        file_inst = form.file.data  # returns the file itself (Filestorage Obj)
        filename = secure_filename(file_inst.filename)  # returns file name as str
        file_path = os.path.join(files_dir, filename)  # returns path as str

        # owner: current user logged in
        owner = int(current_user.get_id())

        date = form.publication_date.data
        date_str = date.strftime('%Y-%m-%d')

        # we create one contributor object with the submitted name
        contributors = [dict(name=form.contributors.data)]

        license_name = None
        for key, value in get_license_mapping().items():
            if isinstance(value, dict):
                for k, v in value.items():
                    if form.license_ref.data == v:
                        license_name = k
            elif isinstance(value, str):
                if form.license_ref.data == value:
                    license_name = key

        data = dict(
                owner=owner,
                upload_type=form.upload_type.data,
                publication_date=date_str,
                title=form.title.data,
                contributors=contributors,

                ethical_issues_exist=form.ethical_issues.data,
                personal_data=form.personal_data.data,
                sensitive_data=form.sensitive_data.data,
                access_right=form.access_right.data,
        )

        if license_name:
            data['license'] = license_name
        if form.description.data:
            data['description'] = form.description.data
        if form.keywords.data:
            data['keywords'] = [form.keywords.data]

        # create the record
        bucket = UploadMaDMP.create_record(
            **data
        )

        UploadMaDMP.create_object(bucket, filename, file_inst)

        # redirect to the success page
        return redirect(url_for('maDMP.success'))

    return render_template('invenio_madmp/create.html', form=form)


@blueprint.route("/success")
@login_required
def success():
    """View for successful upload."""
    return render_template('invenio_madmp/success.html')


@blueprint.route('<rec_id>/upload/file', methods=['GET', 'POST'])
@login_required
def upload_file(rec_id):
    """Attaches the file to the current record."""
    file_form = FileForm()

    if request.method == 'POST':
        if file_form.validate_on_submit():
            if 'file' not in request.files:
                flash('No file part')
                return redirect(request.url)

            file = request.files['file']
            if file.filename == '':
                flash('No selected file')
                return redirect(request.url)

            if file:
                filename = secure_filename(file.filename)

                query = "SELECT json FROM records_metadata WHERE json ->> 'id' = :id"
                result = query_db(query, **{'id': str(rec_id)})

                bucket = result.get('json').get('_bucket')

                UploadMaDMP.create_object(bucket, filename, file)

                flash('File successfully uploaded')
                return redirect(url_for('invenio_records_ui.recid', pid_value=str(rec_id)))

    return render_template('invenio_madmp/upload.html', file_form=file_form, rec_id=rec_id)


@blueprint.route('<int:rec_id>/export/<string:format>', methods=['GET'])
def export(rec_id, format=None):
    """Metadata export."""
    try:
        query = "SELECT * FROM records_metadata WHERE json ->> 'id' = :id"
        result = query_db(query, **{'id': str(rec_id)})

        if not result:
            raise Exception

    except Exception:
        abort(404)
    else:
        if format not in valid_formats():
            error = Error(400, "Invalid Format")
            error_response = error.make_error()
            return error_response

        record_json = result
        record_json['metadata'] = record_json.pop('json')

        return render_template(
            'invenio_madmp/export.html',
            record=json.dumps(record_json, indent=2, default=str),
            rec_id=rec_id
        )


@blueprint.route('<int:rec_id>/export/<string:format>/download', methods=['GET'])
def download(rec_id, format=None):
    """Sends a file for download containing the metadata."""
    try:
        query = "SELECT json FROM records_metadata WHERE json ->> 'id' = :id"
        result = query_db(query, **{'id': str(rec_id)})

        if not result:
            raise Exception

    except Exception:
        abort(404)
    else:
        if format not in valid_formats():
            error = Error(400, "Invalid Format")
            error.make_error()

        record_json = result.pop('json')

        dmp_children = (
            'contact', 'contributors', 'ethical_issues_exist'
        )
        dt_lvl1_children = (
            'description', 'personal_data', 'publication_date',
            'sensitive_data', 'title'
        )
        dt_lvl2_children = (
            'access_url', 'available_until', 'size',
            'data_access', 'download_url', 'format',
            'license',
        )

        data = {'dmp': {}}  # parent dictionary

        dataset_dict = {'dataset': []}
        dataset_fields = {}  # dataset as object

        distribution_dict = {'distribution': []}
        distribution_fields = {}  # distribution as object

        for key in record_json:

            if key in dmp_children:
                data['dmp'].update({key: record_json[key]}) if key != 'contributors' \
                    else data['dmp'].update({key[:-1]: record_json[key]})

            elif key in dt_lvl1_children:
                dataset_fields.update({key: record_json[key]}) if key != 'publication_date' \
                    else dataset_fields.update({'issued': record_json[key]})

            elif key in dt_lvl2_children:
                distribution_fields.update({key: record_json[key]}) \
                    if key != 'license' \
                    else distribution_fields.update(
                    {
                        'license': [{
                            'license_ref': v for k, v in get_license_mapping().items()
                            if k == record_json[key]
                            if not isinstance(v, dict)
                        }]
                    }
                )
            elif key == 'license_start_date':
                distribution_fields.get('license')[0].update({'start_date': record_json[key]})

        distribution_dict['distribution'].append(distribution_fields)
        dataset_fields.update(distribution_dict)

        dataset_dict['dataset'].append(dataset_fields)
        data['dmp'].update(dataset_dict)

        response = make_response(data)
        response.mimetype = 'application/json'

        filename = str(record_json['title'] + '-maDMP.json').replace(" ", "_")
        response.headers['Content-Disposition'] = 'attachment; filename=%s' % filename
        return response
