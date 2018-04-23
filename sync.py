import json
import base64
from time import sleep

import requests
import xml.etree.ElementTree as eTree

from salesforce_bulk import *
import lib
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from salesforce_bulk import SalesforceBulk

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class Service:
    def __init__(self, settings):
        self.user = settings.attrib["user"]
        self.password = settings.attrib["password"]
        self.url = settings.attrib["url"]


class Device42(Service):
    def request(self, path, method, data=()):
        headers = {
            'Authorization': 'Basic ' + base64.b64encode((self.user + ':' + self.password).encode()).decode(),
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        result = None

        if method == 'GET':
            response = requests.get(self.url + path,
                                    headers=headers, verify=False)
            result = json.loads(response.content.decode())
        return result


class Salesforce:
    def __init__(self, settings):
        self.username = settings.attrib["username"]
        self.password = settings.attrib["password"]
        self.organizationId = settings.attrib["organizationId"]

    def request(self, data=()):
        # use csv iterator
        csv_iter = CsvDictsAdapter(iter(data))

        bulk = SalesforceBulk(username=self.username, password=self.password,
                              organizationId=self.organizationId)

        job = bulk.create_insert_job('SamanageCMDB__AgentPost__c', contentType='CSV')
        batch = bulk.post_batch(job, csv_iter)
        bulk.wait_for_batch(job, batch)
        bulk.close_job(job)

        while not bulk.is_batch_done(batch):
            sleep(10)


def init_services(settings):
    return {
        'salesforce': Salesforce(settings.find('salesforce')),
        'device42': Device42(settings.find('device42'))
    }


def task_execute(task, services):
    print('Execute task:', task.attrib['description'])

    _resource = task.find('api/resource')
    _target = task.find('api/target')

    if _resource.attrib['target'] == 'salesforce':
        resource_api = services['salesforce']
        target_api = services['device42']
    else:
        resource_api = services['device42']
        target_api = services['salesforce']

    mapping = task.find('mapping')
    source_url = _resource.attrib['path']
    if _resource.attrib.get("extra-filter"):
        source_url += _resource.attrib.get("extra-filter") + "&amp;"
    source = resource_api.request(source_url, _resource.attrib['method'])
    lib.from_d42(source, mapping, _target, _resource, target_api, resource_api)


print('Running...')

# Load mapping
config = eTree.parse('mapping.xml')
meta = config.getroot()

services = init_services(meta.find('settings'))

# Parse tasks
tasks = meta.find('tasks')
for task in tasks:
    if task.attrib['enable'] == 'true':
        task_execute(task, services)
