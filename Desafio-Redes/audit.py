import json
from pathlib import Path
from ipaddress import IPv4Network


GOLDEN_PATH = Path(__file__).resolve().parent / "config" / "golden_config.json"


def load_golden_config():
    with GOLDEN_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def get_interfaces(client):
    data = client.get("ietf-interfaces:interfaces", params={"content": "config"})
    return data["ietf-interfaces:interfaces"].get("interface", [])


def normalize_addresses(interface):
    addresses = interface.get("ietf-ip:ipv4", {}).get("address", [])
    result = []
    for address in addresses:
        mask = address.get("netmask", address.get("prefix-length"))
        if mask is not None:
            prefix = IPv4Network(f"0.0.0.0/{mask}").prefixlen
            result.append(f"{address['ip']}/{prefix}")
        else:
            result.append(f"{address['ip']}/unknown")
    return sorted(result)


def audit_configuration(client):
    golden = load_golden_config()
    current_interfaces = {interface["name"]: interface for interface in get_interfaces(client)}
    results = []

    for expected in golden["interfaces"]:
        name = expected["name"]
        current = current_interfaces.get(name)
        if current is None:
            results.append({
                "interface": name, "parameter": "existence",
                "expected": True, "actual": False, "compliant": False
            })
            continue

        ipv4 = expected["ipv4"]
        prefix = IPv4Network(f"0.0.0.0/{ipv4['netmask']}").prefixlen
        checks = {
            "description": (expected["description"], current.get("description")),
            # ietf-interfaces defines enabled default true; verify deviations on IOS XE.
            "enabled": (expected["enabled"], current.get("enabled", True)),
            "ipv4": ([f"{ipv4['ip']}/{prefix}"], normalize_addresses(current))
        }
        for parameter, (expected_value, actual_value) in checks.items():
            results.append({
                "interface": name, "parameter": parameter,
                "expected": expected_value, "actual": actual_value,
                "compliant": expected_value == actual_value
            })
    return results
