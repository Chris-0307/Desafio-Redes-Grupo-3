"""Simulador en memoria: no realiza trafico de red."""
from copy import deepcopy
from provisioning import BASE, KEY, MOTD


class MockRouter:
    is_mock = True

    def __init__(self):
        self.interfaces = [{'name': 'Loopback100', 'description': 'Managed by Network Manager',
                            'type': 'iana-if-type:softwareLoopback', 'enabled': True,
                            'ietf-ip:ipv4': {'address': [{'ip': '10.100.0.1', 'netmask': '255.255.255.255'}]}}]
        self.banner = ''
        self.calls = []

    def get(self, endpoint, params=None):
        self.calls.append(('GET', endpoint))
        if endpoint == BASE:
            return {BASE: {'interface': deepcopy(self.interfaces)}}
        if endpoint == MOTD:
            return {'Cisco-IOS-XE-native:motd': {'banner': self.banner}}
        raise ValueError('Endpoint no soportado')

    def _find(self, endpoint):
        name = endpoint.split('interface=', 1)[1].split('/')[0]
        return next(i for i in self.interfaces if i['name'] == name)

    def post(self, endpoint, payload):
        self.calls.append(('POST', endpoint))
        if endpoint != BASE:
            raise ValueError('Endpoint no soportado')
        new = deepcopy(payload[KEY][0])
        if any(i['name'] == new['name'] for i in self.interfaces):
            raise ValueError('Ya existe')
        self.interfaces.append(new)
        return 201

    def patch(self, endpoint, payload):
        self.calls.append(('PATCH', endpoint))
        self._find(endpoint).update(deepcopy(payload[KEY][0]))
        return 204

    def yang_patch(self, endpoint, payload):
        self.calls.append(('PATCH (YANG)', endpoint))
        edit = payload['ietf-yang-patch:yang-patch']['edit'][0]
        if edit['operation'] != 'replace' or edit['target'] != '/ietf-ip:ipv4':
            raise ValueError('Edicion no soportada')
        self._find(endpoint)['ietf-ip:ipv4'] = deepcopy(edit['value']['ietf-ip:ipv4'])
        return 204

    def put(self, endpoint, payload):
        self.calls.append(('PUT', endpoint))
        if endpoint == MOTD:
            self.banner = payload['Cisco-IOS-XE-native:motd']['banner']
        elif endpoint.endswith('/description'):
            self._find(endpoint)['description'] = payload['ietf-interfaces:description']
        else:
            raise ValueError('Endpoint no soportado')
        return 204

    def simulate_drift(self, kind='basic'):
        interface = self._find(BASE + '/interface=Loopback100')
        if kind in ('basic', 'all'):
            interface['enabled'] = False
            interface['description'] = 'Unauthorized configuration'
        if kind in ('ip', 'all'):
            interface['ietf-ip:ipv4']['address'] = [{'ip': '10.100.0.99', 'netmask': '255.255.255.255'}]
