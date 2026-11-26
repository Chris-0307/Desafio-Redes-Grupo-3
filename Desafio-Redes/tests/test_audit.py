import unittest
from audit import audit_configuration
from mock_router import MockRouter


class TestAudit(unittest.TestCase):
    def test_compliant(self):
        results = audit_configuration(MockRouter())
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r["compliant"] for r in results))

    def test_drift(self):
        router = MockRouter()
        router.simulate_drift()
        results = audit_configuration(router)
        self.assertEqual({r["parameter"] for r in results if not r["compliant"]}, {"description", "enabled"})

    def test_prefix_length(self):
        router = MockRouter()
        router.interfaces[0]["ietf-ip:ipv4"]["address"] = [{"ip": "10.100.0.1", "prefix-length": 32}]
        self.assertTrue(all(r["compliant"] for r in audit_configuration(router)))

    def test_ip_drift(self):
        router = MockRouter()
        router.interfaces[0]["ietf-ip:ipv4"]["address"][0]["ip"] = "10.100.0.2"
        self.assertEqual([r["parameter"] for r in audit_configuration(router) if not r["compliant"]], ["ipv4"])

    def test_missing_interface(self):
        router = MockRouter()
        router.interfaces.clear()
        results = audit_configuration(router)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["parameter"], "existence")
        self.assertFalse(results[0]["compliant"])


if __name__ == "__main__":
    unittest.main()
