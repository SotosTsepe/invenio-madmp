# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Sotirios Tsepelakis.
#
# invenio-maDMP is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Views for deposit of records."""

from __future__ import absolute_import, print_function

import os

from flask import Blueprint, abort, current_app, flash, \
    make_response, redirect, render_template, request, url_for
from flask_login import login_required
from flask_security import current_user
from invenio_db import db
from sqlalchemy import text
from werkzeug.utils import secure_filename

from .api import UploadMaDMP
from .forms import MaDMPForm, FileForm

# define a new Flask Blueprint that is registered under the url path /madmp
blueprint = Blueprint(
    'maDMP',
    __name__,
    url_prefix='/madmp',
    template_folder='templates',
    static_folder='static',
)


def valid_formats():
    """
    Defines valid formats for export

    :returns: Tuple with valid formats
    """

    return ('json',)


def query_db(query, **kwargs):
    """
    Make a query to the Invenio DB

    :param query: Query to run
    :returns: Result of the query as RowProxy Instance
    """

    result = db.session.execute(text(query), kwargs)
    return result


@blueprint.route('/upload', methods=('GET', 'POST'))
@login_required
def create():
    """The create view."""

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

        upload_type = form.upload_type.data

        date = form.publication_date.data
        date_str = date.strftime('%Y-%m-%d')

        # we create one contributor object with the submitted name
        contributors = [dict(name=form.contributors.data)]
        description = form.description.data
        keywords = [form.keywords.data]

        access_right = form.access_right.data

        for key, value in UploadMaDMP.license_mapping.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    if form.license_ref.data == v:
                        license_name = k
            elif isinstance(value, str):
                if form.license_ref.data == value:
                    license_name = key

        # create the record
        bucket = UploadMaDMP.create_record(
            dict(
                title=form.title.data,
                upload_type=upload_type,
                contributors=contributors,
                owner=owner,
                publication_date=date_str,
                access_right=access_right,
                license=license_name,
                # description=description
            )
        )

        UploadMaDMP.create_object(bucket, filename, file_inst)

        # redirect to the success page
        return redirect(url_for('maDMP.success'))

    return render_template('maDmp/create.html', form=form)


@blueprint.route("/success")
@login_required
def success():
    """Success view."""
    return render_template('maDmp/success.html')


# TODO: better UX: extend current records' URL
@blueprint.route('<rec_id>/upload/file', methods=['GET', 'POST'])
@login_required
def upload_file(rec_id):
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

            # TODO: Handle file is bigger error
            if file:
                filename = secure_filename(file.filename)

                '''result = RecordMetadata.query.filter(
                    RecordMetadata.json['id'] == cast(session.get('rec_id'), JSONB)
                ).one_or_none()'''

                # result = (RecordMetadata.query.filter(text("CAST(json->>'id' AS INTEGER) = 2"))).first()
                # < RecordMetadata ...uuid... >
                # RecordMetadata.query.first().json['id']

                query = "SELECT json FROM records_metadata WHERE json ->> 'id' = :id"
                result = query_db(query, **{'id': str(rec_id)})

                record_json_list = [{column: value for column, value in rowproxy.items()} for rowproxy in result]
                record_json = record_json_list.pop(0)
                bucket = record_json.get('json').get('_bucket')

                UploadMaDMP.create_object(bucket, filename, file)

                flash('File successfully uploaded')
                return redirect(url_for('invenio_records_ui.recid', pid_value=str(rec_id)))

    return render_template('maDmp/upload.html', file_form=file_form, rec_id=rec_id)


@blueprint.route('<int:rec_id>/export/<string:format>', methods=['GET'])
def export(rec_id, format=None):
    if not format:
        abort(400, 'No format selected')

    if format not in valid_formats():
        return render_template('maDmp/errors/wrong_format_400.html')

    query = "SELECT * FROM records_metadata WHERE json ->> 'id' = :id"
    result = query_db(query, **{'id': str(rec_id)})

    record_json_list = [{column: value for column, value in rowproxy.items()} for rowproxy in result]
    record_json = record_json_list.pop(0)
    record_json['metadata'] = record_json.pop('json')
    print(record_json)
    return render_template('maDmp/export.html', json=record_json, rec_id=rec_id)


@blueprint.route('<int:rec_id>/export/<string:format>/download', methods=['GET'])
def download(rec_id, format=None):

    if format not in valid_formats():
        return render_template('maDmp/errors/wrong_format_400.html')

    query = "SELECT json FROM records_metadata WHERE json ->> 'id' = :id"
    result = query_db(query, **{'id': str(rec_id)})

    record_json_list = [{column: value for column, value in rowproxy.items()} for rowproxy in result]
    record_json = record_json_list.pop(0)
    record_json = record_json.pop('json')

    dt_lvl1_children = (
        'description', 'personal_data', 'publication_date'
        'sensitive_data', 'title'
    )
    dt_lvl2_children = (
        'access_url', 'available_until', 'size',
        'data_access', 'download_url', 'format',
        'license'
    )

    data = {'dmp': {}}  # parent dictionary

    dataset_dict = {'dataset': []}
    dataset_fields = {}  # dataset as object

    distribution_dict = {'distribution': []}
    distribution_fields = {}  # distribution as object

    for key in record_json:

        if key == 'contributors':
            data['dmp'].update({key[:-1]: record_json[key]})

        elif key in dt_lvl1_children:
            dataset_fields.update({key: record_json[key]}) if key != 'publication_date' \
                else dataset_fields.update({'issued': record_json[key]})

        elif key in dt_lvl2_children:
            distribution_fields.update({key: record_json[key]})

    distribution_dict['distribution'].append(distribution_fields)
    dataset_fields.update(distribution_dict)

    dataset_dict['dataset'].append(dataset_fields)
    data['dmp'].update(dataset_dict)

    response = make_response(data)
    response.mimetype = 'application/json'
    response.headers['Content-Disposition'] = 'attachment; filename=maDMP.json'
    return response
