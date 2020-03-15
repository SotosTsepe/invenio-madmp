# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Sotiris Tsepelakis.
#
# invenio-maDMP is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.

"""MaDMP REST API"""

import json
import os
import uuid

from flask import Blueprint, jsonify, request
from invenio_db import db
from invenio_files_rest.models import ObjectVersion, Bucket
from invenio_files_rest.serializer import json_serializer
from invenio_files_rest.signals import file_uploaded
from invenio_indexer.api import RecordIndexer
from invenio_pidstore import current_pidstore
from invenio_records.api import Record
from invenio_records_files.api import Record
from invenio_rest import ContentNegotiatedMethodView
from json import JSONDecodeError
from jsonschema import validate, ValidationError, FormatChecker
from werkzeug.exceptions import BadRequest


blueprint = Blueprint(
    'madmp',
    __name__,
    url_prefix='/madmp',
    template_folder='templates'
)


def get_license_mapping():
    license_mapping = {
        'Apache License 2.0': 'https://opensource.org/licenses/Apache-2.0',
        '3-Clause BSD License': 'https://opensource.org/licenses/BSD-3-Clause',
        '2-Clause BSD License': 'https://opensource.org/licenses/BSD-2-Clause',
        'GNU General Public License': {
            'GNU Library General Public License version 2': 'https://opensource.org/licenses/LGPL-2.0',
            'GNU Lesser General Public License version 2.1': 'https://opensource.org/licenses/LGPL-2.1',
            'GNU Lesser General Public License version 3': 'https://opensource.org/licenses/LGPL-3.0'
        },
        'GNU LGPL': {
            'GNU General Public License version 2': 'https://opensource.org/licenses/GPL-2.0',
            'GNU General Public License version 3': 'https://opensource.org/licenses/GPL-3.0'
        },
        'MIT': 'https://opensource.org/licenses/MIT',
        'Mozilla Public License 2.0': 'https://opensource.org/licenses/MPL-2.0',
        'Common Development and Distribution License 1.0': 'https://opensource.org/licenses/CDDL-1.0',
        'Eclipse Public License version 2.0': 'https://opensource.org/licenses/EPL-2.0',

        'CC BY': 'https://creativecommons.org/licenses/by/4.0/',
        'CC BY-SA': 'https://creativecommons.org/licenses/by-sa/4.0/',
        'CC BY-ND': 'https://creativecommons.org/licenses/by-nd/4.0/',
        'CC BY-NC': 'https://creativecommons.org/licenses/by-nc/4.0/',
        'CC BY-NC-SA': 'https://creativecommons.org/licenses/by-nc-sa/4.0/',
        'CC BY-NC-ND': 'https://creativecommons.org/licenses/by-nc-nd/4.0/'
    }
    return license_mapping


class UploadMaDMP(ContentNegotiatedMethodView):
    """Validate madmp file or raw JSON and upload metadata"""

    def post(self):
        """
        Create new object version from the file in the given path.

        Verify first, if the file validates against the maDMP schema.
        Then store its metadata.

        :returns: Created Record View
        """

        global json_data
        path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filename = 'maDMP-schema.json'

        try:
            with open(os.path.join(path, filename)) as json_file:
                schema_data = json.load(json_file)
        except IOError as io_exc:
            response = jsonify({'message': 'Something went wrong', 'status': 500})
            response.status_code = 500
            print(io_exc)
            return response

        try:
            if 'file' not in request.files and not request.json:
                raise BadRequest('No file or json data in request')

            if 'file' in request.files and request.json:
                raise BadRequest('Only file or data must be in request')

            if 'file' in request.files:
                file = request.files['file']  # FileStorage Object

                if file.filename == '':
                    raise BadRequest('No file selected')

                if len(file.read()) is 0:
                    raise BadRequest('File is empty')

                json_data = json.load(file)

            elif request.json:
                json_data = request.json

                if json_data is None:
                    raise BadRequest('JSON data is empty')

            validate(instance=json_data, schema=schema_data, format_checker=FormatChecker())

        except BadRequest as bad_req_exc:
            response = jsonify({'message': bad_req_exc.description, 'status': 400})
            response.status_code = 400
            return response
        except ValidationError as validation_exc:
            response = jsonify({
                'message': 'JSON does not validate against the schema',
                'details': validation_exc.message,
                'status': 400
            })
            response.status_code = 400
            return response
        except JSONDecodeError as json_exc:
            response = jsonify({'message': 'JSON syntax error: ' + json_exc.msg, 'status': 400})
            response.status_code = 400
            print(json_exc)
            return response
        except IOError:
            response = jsonify({'message': 'Error processing file', 'status': 500})
            response.status_code = 500
            return response
        except Exception as exc:
            response = jsonify({'message': 'Something went wrong', 'status': 500})
            response.status_code = 500
            print(exc.__str__())
            return response
        else:
            try:
                data = UploadMaDMP.extract_data(json_data)
                if not data:
                    raise BadRequest
            except BadRequest:
                response = jsonify({
                    'message': 'Could not extract any data. Check again your json structure',
                    'status': 400
                })
                response.status_code = 400
                return response
            except Exception as exc:
                response = jsonify({'message': 'Something went wrong', 'status': 500})
                response.status_code = 500
                print('Extact data method: ' + exc.__str__())
                return response

        calls = 1
        responses = {'responses': []}

        for rec in data:
            try:
                _ = UploadMaDMP.create_record(rec)
            except Exception as exc:
                response = {'id': calls, 'message': 'Something went wrong', 'status': 500}
                responses['responses'].append(response)
                print("Error inserting record: " + exc.__str__())
            else:
                response = {'id': calls, 'message': 'Metadata created successfully', 'status': 201}
                responses['responses'].append(response)

            calls += 1

        resp = jsonify(responses)
        resp.status_code = 201 if not any(item['status'] == 500 for item in responses['responses']) else 500
        return resp

    @staticmethod
    def validate_license(value):
        """
        Checks if the License Reference is correct.

        :param value: URL of license
        :returns: True if license is found in the mapping, False otherwise.
        """

        if value in get_license_mapping().values():
            return True

        for k, v in get_license_mapping().items():
            if isinstance(v, dict):
                if value in v.values():
                    return True

        return False

    @staticmethod
    def extract_data(all_data):
        """
        Get only specific data from DMP to store.

        :param all_data: dictionary with JSON data
        :returns: dictionary with certain extracted values, None if the structure is not valid
        """

        def dataset_prim_keys():
            return ('title', 'issued', 'type', 'personal_data', 'sensitive_data', 'description')

        def split_datasets():
            final_values = []

            for dt in range(1, dataset_counter):
                tmp = {}

                for field in list(desired_values):
                    if field != 'dataset' + str(dt):
                        tmp.update({field: desired_values[field]})
                    else:
                        tmp.update(desired_values.pop('dataset' + str(dt)))
                        break

                final_values.append(tmp)

            return final_values

        desired_values = {}

        if all_data.get('dmp'):

            for field in all_data['dmp']:
                if field == 'ethical_issues_exist':
                    desired_values.update({field: all_data['dmp'][field]})

                elif field == 'contact':

                    temp = {field: {}}

                    for key in all_data['dmp'][field]:

                        if key == 'name' or key == 'mbox':
                            temp[field].update({key: all_data['dmp'][field][key]})

                    desired_values.update(temp)

                elif field == 'contributor':
                    temp1 = {}
                    temp2 = {field + 's': []}

                    for item in all_data['dmp'][field]:

                        for key in item:
                            if key == 'name' or key == 'mbox' or key == 'role':
                                if key == 'mbox':
                                    temp1.update({'email': item[key]})
                                else:
                                    temp1.update({key: item[key]})

                        temp2[field + 's'].append(temp1.copy())

                    desired_values.update(temp2)

                elif field == 'dataset':
                    temp = {}

                    # initialize dataset dicts
                    for x in range(1, len(all_data['dmp'][field]) + 1):
                        temp.update({
                            field + str(x): {}
                        })
                    dataset_counter = 1

                    # loop through dataset objects
                    for dataset in all_data['dmp'][field]:
                        license_exists = False

                        # loop through object keys
                        for key in dataset:

                            if not isinstance(dataset[key], (dict, list)):
                                if key in dataset_prim_keys():
                                    temp[field + str(dataset_counter)].update({'upload_type': dataset[key]}) \
                                        if key == 'type'\
                                        else temp[field + str(dataset_counter)].update({key: dataset[key]})

                            elif isinstance(dataset[key], list) and key == 'distribution':
                                temp2 = []
                                for item2 in dataset[key]:  # distribution obj

                                    for key2 in item2:  # distribution key

                                        if key2 == 'data_access':
                                            temp[field + str(dataset_counter)].update({key2: item2[key2]})

                                        # license is array so more nested loops are needed
                                        elif key2 == 'license':
                                            license_exists = True
                                            license_fields = ('license_ref', 'start_date')

                                            for dt_license in item2[key2]:
                                                for key3 in dt_license:

                                                    if key3 == 'license_ref':
                                                        if not UploadMaDMP.validate_license(dt_license[key3]):
                                                            continue

                                                        temp2.append({key3: dt_license[key3]})

                                                    elif key3 == 'start_date':
                                                        temp[field + str(dataset_counter)].update(
                                                            {'license_' + key3: dt_license[key3]}
                                                        )

                                            # check if license was appended and re-append
                                            if len(temp2) is not 0:
                                                temp[field + str(dataset_counter)].update({key2: temp2})

                        if 'issued' in temp[field + str(dataset_counter)]:
                            # rename key issued to publication_date
                            temp[field + str(dataset_counter)]['publication_date'] = \
                                temp[field + str(dataset_counter)].pop('issued')

                        if license_exists and len(temp2) is not 0:
                            found = False
                            for k in get_license_mapping():
                                if found: break

                                if isinstance(get_license_mapping()[k], dict):
                                    for k_nested in get_license_mapping()[k]:
                                        if get_license_mapping()[k][k_nested] == \
                                                temp[field + str(dataset_counter)].get('license')[0].get('license_ref'):

                                            temp[field + str(dataset_counter)]['license'] = k_nested
                                            found = True
                                            break
                                else:
                                    if get_license_mapping()[k] == \
                                            temp[field + str(dataset_counter)].get('license')[0].get('license_ref'):

                                        temp[field + str(dataset_counter)]['license'] = k
                                        break

                        dataset_counter += 1

                    desired_values.update(temp)

        return split_datasets() if desired_values else None

    @staticmethod
    def create_record(data):
        """
        Insert the record

        :param data: Record data
        :returns: Created Record's Bucket ID
        """

        with db.session.begin_nested():
            rec_uuid = uuid.uuid4()
            current_pidstore.minters['recid'](rec_uuid, data)
            created_record = Record.create(data, id_=rec_uuid)
            RecordIndexer().index(created_record)

        db.session.commit()

        return created_record.get('_bucket')

    @staticmethod
    def create_object(bucket, key, file_instance):
        """
        Upload the file

        :param bucket: the bucket id or instance
        :param key: the file name
        :param file_instance: the file object
        """

        if isinstance(bucket, str):
            size_limit = Bucket.get(bucket).size_limit
        else:
            size_limit = bucket.size_limit

        with db.session.begin_nested():
            obj = ObjectVersion.create(bucket, key)
            obj.set_contents(
                stream=file_instance.stream,
                size_limit=size_limit
            )

        db.session.commit()
        file_uploaded.send(obj)


upload_view = UploadMaDMP.as_view(
    'validation',
    serializers={
        'application/json': json_serializer
    }
)

blueprint.add_url_rule(
    '/upload',
    view_func=upload_view,
    methods=['POST'],
)
