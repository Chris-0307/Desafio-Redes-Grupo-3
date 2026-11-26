import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
import os
from audit import audit_configuration
from mock_router import MockRouter
from remediation import repair
from provisioning import create_loopback, change_description, put_description, update_banner, setup_managed
from reporting import Reporter
from restconf_client import RestconfClient


class TestSystem(unittest.TestCase):
    def test_remediation_all(self):
        r = MockRouter(); r.simulate_drift('all')
        results = repair(r, audit_configuration(r))
        self.assertEqual(len(results), 3)
        self.assertTrue(all(x['success'] for x in results))
        self.assertTrue(all(x['compliant'] for x in audit_configuration(r)))
        self.assertTrue(any(x[0] == 'PATCH (YANG)' for x in r.calls))

    def test_extra_ip_removed(self):
        r = MockRouter()
        r.interfaces[0]['ietf-ip:ipv4']['address'].append({'ip':'10.100.0.99','netmask':'255.255.255.255'})
        self.assertTrue(repair(r, audit_configuration(r))[0]['success'])
        self.assertEqual(len(r.interfaces[0]['ietf-ip:ipv4']['address']),1)

    def test_missing_not_created_automatically(self):
        r = MockRouter(); r.interfaces.clear()
        self.assertFalse(repair(r, audit_configuration(r))[0]['success'])
        self.assertEqual(r.interfaces, [])
        self.assertEqual(setup_managed(r), 201)

    def test_provisioning(self):
        r = MockRouter()
        self.assertEqual(create_loopback(r,'Loopback101','demo','10.101.0.1/32'),201)
        self.assertEqual(change_description(r,'Loopback101','new'),204)
        self.assertEqual(put_description(r,'newer'),204)
        self.assertEqual(update_banner(r,'hello'),204)
        self.assertEqual(r.banner,'hello')
        self.assertTrue(all(x['compliant'] for x in audit_configuration(r)))
        with self.assertRaises(ValueError):
            create_loopback(r,'Loopback101','duplicate','10.101.0.2/32')

    def test_scope(self):
        r = MockRouter()
        with self.assertRaises(ValueError):
            create_loopback(r,'GigabitEthernet1','x','10.0.0.1/32')

    def test_verification_failure(self):
        r = MockRouter(); r.simulate_drift()
        with patch.object(r,'patch',return_value=204):
            self.assertTrue(all(not x['success'] for x in repair(r,audit_configuration(r))))

    def test_report(self):
        with TemporaryDirectory() as path:
            r = MockRouter(); r.simulate_drift()
            rep = Reporter('MOCK',path)
            rows = audit_configuration(r); rep.audit(rows)
            rep.remediation(repair(r,rows),audit_configuration(r))
            self.assertEqual(rep.summary()['successful_remediations'],2)
            self.assertEqual(rep.summary()['last_verified_compliance_percent'],100)
            self.assertTrue(all(p.exists() for p in rep.export()))

    def test_real_write_guard(self):
        with patch.dict(os.environ, {'ROUTER_HOST':'example.invalid','ROUTER_USERNAME':'test','ROUTER_PASSWORD':'test','ALLOW_WRITES':'false'}):
            r=RestconfClient()
            with patch.object(r.session,'request') as request:
                with self.assertRaises(ValueError):
                    r.patch('example',{})
                request.assert_not_called()

    def test_connection_error_no_writes(self):
        r = MockRouter()
        with patch.object(r,'get',side_effect=ConnectionError('offline')):
            with self.assertRaises(ConnectionError):
                audit_configuration(r)
        self.assertFalse(any(x[0] != 'GET' for x in r.calls))

if __name__ == '__main__': unittest.main()
