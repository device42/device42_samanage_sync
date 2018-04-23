import json
import sys
from importlib import reload

reload(sys)

DEBUG = True

object_keys = [
    "Hardware", "Cpu", "Controller", "Display", "Drive", "Input", "Memory", "Network", "Port",
    "Printer", "Software", "Sound", "Storage", "Video"
]


def fill_ci_body_imem(data, subfields):
    data_el = {}
    for key, value in data.items():
        for field in subfields:
            if key == field.attrib.get('resource'):
                if field.attrib.get('sub-resource'):
                    value = value[field.attrib.get('sub-resource')]
                data_el[field.attrib.get('target')] = value
    return data_el


def complete_batch_object_body(body):
    body_keys = body.keys()
    for key in object_keys:
        if key not in body_keys:
            data = []
            body[key] = {
                "data": data,
                "metadata": {
                    "status": "OK",
                    "data_hash": str(
                        hash(json.dumps(data)) if hash(json.dumps(data)) > 0 else hash(json.dumps(data)) + sys.maxsize)
                }
            }
    bios_data = [{"serial_number": "N/A"}]
    body["Bios"] = {
        "data": bios_data,
        "metadata": {
            "status": "OK",
            "data_hash": str(hash(json.dumps(bios_data)) if hash(json.dumps(bios_data)) > 0 else hash(
                json.dumps(bios_data)) + sys.maxsize)
        }
    }
    return body


def fill_batch_object(fields, match_map, source_api):
    body = {}
    data = fields
    for key, value in fields.items():
        val = ''
        if key in match_map:
            if match_map[key].attrib.get("url"):
                url = match_map[key].attrib.get("url")
                if match_map[key].attrib.get("extra-api-additional-param"):
                    url = "{}{}".format(url, data[match_map[key].attrib.get("extra-api-additional-param")])
                response = source_api.request(url, 'GET')
                if match_map[key].findall('sub-field'):
                    if match_map[key].attrib.get('target-ci-type') not in body:
                        body[match_map[key].attrib.get('target-ci-type')] = {'data': []}
                    sub_data = response
                    if match_map[key].attrib.get('sub-key'):
                        sub_data = response[match_map[key].attrib.get('sub-key')]
                    for el in sub_data:
                        body[match_map[key].attrib.get('target-ci-type')]['data'].append(
                            fill_ci_body_imem(el, match_map[key].findall('sub-field')))
            if data.get(match_map[key].attrib['resource']) and not match_map[key].findall('sub-field'):
                val = data[match_map[key].attrib['resource']]
                if match_map[key].get("is-array") and val:
                    val = val[0]
                if match_map[key].get("sub-key"):
                    val = val[match_map[key].get("sub-key")]
                if key == "FriendlyName" and not val:
                    val = data["name"]
            if match_map[key].findall('sub-field') and not match_map[key].attrib.get("url"):
                if match_map[key].attrib.get('target-ci-type') not in body:
                    body[match_map[key].attrib.get('target-ci-type')] = {'data': []}
                sub_data = data[match_map[key].attrib['resource']]
                for el in sub_data:
                    body[match_map[key].attrib.get('target-ci-type')]['data'].append(
                        fill_ci_body_imem(el, match_map[key].findall('sub-field')))
        if val:
            if match_map[key].attrib.get('type') == 'integer':
                val = int(val)
            if match_map[key].attrib.get('target-ci-type') not in body:
                body[match_map[key].attrib.get('target-ci-type')] = {"data": [{}]}
            body[match_map[key].attrib.get('target-ci-type')]['data'][0][match_map[key].attrib.get('target')] = val
    for key, item in body.items():
        # if item.get('data'):
        item['metadata'] = {
            'data_hash': str(hash(json.dumps(item['data'])) if hash(json.dumps(item['data'])) > 0 else hash(
                json.dumps(item['data'])) + sys.maxsize),
            'status': 'OK'
        }
    body = complete_batch_object_body(body)

    response_object = {
        'Name': fields['name'],
        'SamanageCMDB__CustomExtIdField__c': '{}{}'.format('D42', fields['device_id']),
        'SamanageCMDB__JsonData__c': json.dumps({
            'vendor': 1,
            'body_version': 1,
            "body": body
        })
    }

    return response_object


def perform_butch_request(mapping, match_map, _target, _resource, source, target_api,
                          resource_api):
    offset = source.get("offset", 0)
    limit = source.get("limit", 500)
    batch = []
    for idx, item in enumerate(source[mapping.attrib['source']]):
        print("Processing {} of {} records".format(int(offset) + idx + 1, source["total_count"]))
        batch.append(
            fill_batch_object(item, match_map, resource_api))

    target_api.request(batch)

    if offset + limit < source["total_count"]:
        print("Exported {} of {} records".format(offset + limit, source["total_count"]))
        source_url = _resource.attrib['path']
        if _resource.attrib.get("extra-filter"):
            source_url += _resource.attrib.get("extra-filter") + "&amp;"
        source = resource_api.request(
            "{}offset={}".format(source_url, offset + limit),
            _resource.attrib['method'])
        perform_butch_request(mapping, match_map, _target, _resource, source,
                              target_api,
                              resource_api)
    return True


def from_d42(source, mapping, _target, _resource, target_api, resource_api):
    fields = mapping.findall('field')
    match_map = {field.attrib['resource']: field for field in fields}

    success = perform_butch_request(mapping, match_map, _target, _resource, source, target_api, resource_api)
    if success:
        print("Success")
    else:
        print("Something bad happened")
