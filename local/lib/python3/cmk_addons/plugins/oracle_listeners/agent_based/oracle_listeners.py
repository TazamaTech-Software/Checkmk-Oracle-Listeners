#!/usr/bin/env python3

from collections.abc import Mapping

# Import debug objects, remember the path changed between 2.3.0 and 2.4.0
try:
    from cmk.ccc import debug
except ImportError:
    from cmk.utils import debug

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    StringTable,
)

from cmk_addons.plugins.oracle_listeners.oracle_listeners_metrics import METRIC_DEF

from cmk_addons.plugins.oracle_listeners.agent_based.oracle_listeners_lib import (
    MetricData,
    parse_oracle,
    discover_oracle,
    check_oracle,
    cluster_check_oracle,
)

agent_section_oracle_listeners = AgentSection(
    name = "oracle_listeners",
    parse_function = parse_oracle,
)

_default_parameters = { k: {m: v.get(m, '') for m in ('enabled', 'type', 'critical', 'warning')} for k,v in METRIC_DEF.items() }

# Below is generated code

def discover_oracle_m3000(params, section: Mapping[str, MetricData]) -> DiscoveryResult:
    yield from discover_oracle(params, section, 'm3000')

def check_oracle_m3000(item: str, params, section: Mapping[str, MetricData]) -> CheckResult:
    yield from check_oracle(item, params, section, 'm3000', METRIC_DEF)

def cluster_check_oracle_m3000(item: str, params, section) -> CheckResult:
    yield from cluster_check_oracle(item, params, section, 'm3000', 'WorstOf', METRIC_DEF)

check_plugin_oracle_m3000 = CheckPlugin(
    name = 'oracle_m3000',
    sections = ['oracle_listeners'],
    service_name = 'Oracle Listener %s',
    discovery_function = discover_oracle_m3000,
    discovery_default_parameters = _default_parameters,
    discovery_ruleset_name = 'oracle_listeners_parameters',
    check_function = check_oracle_m3000,
    check_default_parameters = _default_parameters,
    check_ruleset_name = 'oracle_listeners_parameters',
    cluster_check_function = cluster_check_oracle_m3000,
)

def discover_oracle_m3010(params, section: Mapping[str, MetricData]) -> DiscoveryResult:
    yield from discover_oracle(params, section, 'm3010')

def check_oracle_m3010(item: str, params, section: Mapping[str, MetricData]) -> CheckResult:
    yield from check_oracle(item, params, section, 'm3010', METRIC_DEF)

def cluster_check_oracle_m3010(item: str, params, section) -> CheckResult:
    yield from cluster_check_oracle(item, params, section, 'm3010', 'WorstOf', METRIC_DEF)

check_plugin_oracle_m3010 = CheckPlugin(
    name = 'oracle_m3010',
    sections = ['oracle_listeners'],
    service_name = 'Oracle RAC SCAN Listener %s',
    discovery_function = discover_oracle_m3010,
    discovery_default_parameters = _default_parameters,
    discovery_ruleset_name = 'oracle_listeners_parameters',
    check_function = check_oracle_m3010,
    check_default_parameters = _default_parameters,
    check_ruleset_name = 'oracle_listeners_parameters',
    cluster_check_function = cluster_check_oracle_m3010,
)

def discover_oracle_m3020(params, section: Mapping[str, MetricData]) -> DiscoveryResult:
    yield from discover_oracle(params, section, 'm3020')

def check_oracle_m3020(item: str, params, section: Mapping[str, MetricData]) -> CheckResult:
    yield from check_oracle(item, params, section, 'm3020', METRIC_DEF)

def cluster_check_oracle_m3020(item: str, params, section) -> CheckResult:
    yield from cluster_check_oracle(item, params, section, 'm3020', 'WorstOf', METRIC_DEF)

check_plugin_oracle_m3020 = CheckPlugin(
    name = 'oracle_m3020',
    sections = ['oracle_listeners'],
    service_name = 'Oracle Management Listener %s',
    discovery_function = discover_oracle_m3020,
    discovery_default_parameters = _default_parameters,
    discovery_ruleset_name = 'oracle_listeners_parameters',
    check_function = check_oracle_m3020,
    check_default_parameters = _default_parameters,
    check_ruleset_name = 'oracle_listeners_parameters',
    cluster_check_function = cluster_check_oracle_m3020,
)
