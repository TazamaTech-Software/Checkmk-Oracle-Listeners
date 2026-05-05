#!/usr/bin/env python3

from collections.abc import Mapping
from dataclasses import dataclass

# Import debug objects, remember the path changed between 2.3.0 and 2.4.0
try:
    from cmk.ccc import debug
except ImportError:
    from cmk.utils import debug

from pprint import pprint
# How to use custom debug output:
#  if debug.enabled():
#        pprint(section)

from cmk.agent_based.v2 import (
    CheckResult,
    DiscoveryResult,
    Service,
    Result,
    State,
    StringTable,
    Metric,
)

@dataclass
class MetricData:
    obj_name: str
    metric: str
    value: float
    option1: str
    option2: str
    option3: str
    option4: str
    option5: str

def parse_oracle(string_table: StringTable) -> Mapping[str, MetricData]:
# Output on Agent:
# LISTENER:/u01/app/oracle/product/19c/db|3000|0|LSNRNAME=LISTENER|ORAHOME=/u01/...|ERROR=No error|NODE=rac1|None
# LISTENER_SCAN1:/u01/app/oracle/product/19c/grid|3010|0|LSNRNAME=LISTENER_SCAN1|ORAHOME=/u01/...|ERROR=No error|NODE=rac1|None

    if debug.enabled():
        pprint(string_table)

    section = {}
    for obj_name, metric, value, option1, option2, option3, option4, option5 in string_table:
        key = obj_name + ":" + metric
        if key not in section:
            try:
                parsed_value = float(value)
            except (ValueError, TypeError):
                parsed_value = float('nan')
            section[key] = MetricData(
                obj_name = obj_name,
                metric   = 'm' + metric,
                value    = parsed_value,
                option1  = option1,
                option2  = option2,
                option3  = option3,
                option4  = option4,
                option5  = option5,
            )

    if debug.enabled():
        pprint(section)

    return section


def calc_state(mname, value, minmax, crit, warn):
    try:
        fval = float(value)
        fcrit = float(crit) if crit != 'NaN' else None
        fwarn = float(warn) if warn != 'NaN' else None
    except (ValueError, TypeError):
        return State.UNKNOWN

    if minmax == 'MAX':
        if fcrit is not None and fval > fcrit:
            return State.CRIT
        if fwarn is not None and fval > fwarn:
            return State.WARN
    elif minmax == 'MIN':
        if fcrit is not None and fval < fcrit:
            return State.CRIT
        if fwarn is not None and fval < fwarn:
            return State.WARN

    return State.OK


def cluster_calc_state(node_states: dict, algorithm: str):
    if algorithm == 'WorstOf':
        return State.worst(*node_states.values())
    else:
        return State.best(*node_states.values())


def alert_description(data: MetricData, metric_def: dict):
    for metric in metric_def:
        if metric == data.metric:
            desc = metric_def[metric]['alert']
            if desc:
                desc = desc.replace('<MONVALUE>', str(data.value))
                desc = desc.replace('<OBJECT>', str(data.obj_name))
                desc = desc.replace('<THRESHOLD>', str(metric_def[metric]['warning']) + '/' + str(metric_def[metric]['critical']))
                desc = desc.replace('<OPTION1>', str(data.option1))
                desc = desc.replace('<OPTION2>', str(data.option2))
                desc = desc.replace('<OPTION3>', str(data.option3))
                desc = desc.replace('<OPTION4>', str(data.option4))
                desc = desc.replace('<OPTION5>', str(data.option5))
                for option in (data.option1, data.option2, data.option3, data.option4, data.option5):
                    if '=' in option:
                        (key, value) = option.split('=', 1)
                        desc = desc.replace(f'<{key}>', value)
                if debug.enabled():
                    print(f"Alert: {desc}")
                return desc
    if debug.enabled():
        print(f'Undefined alert message for metric {data.metric}')
    return f'Undefined alert message for metric {data.metric}'


def cluster_alert_description(node_metric_data, metric_def):
    text = ", ".join(f"[{node_name}]: {alert_description(metric_data, metric_def)}" for node_name, metric_data in node_metric_data.items())
    return text


def cluster_metric_value(node_metric_data, algorithm, minmax):
    if algorithm == 'WorstOf':
        if minmax == 'MIN':
            return float(min(v.value for v in node_metric_data.values()))
        else:
            return float(max(v.value for v in node_metric_data.values()))
    else:
        if minmax == 'MIN':
            return float(max(v.value for v in node_metric_data.values()))
        else:
            return float(min(v.value for v in node_metric_data.values()))


def discover_oracle(params: dict, section: Mapping[str, MetricData], metric: str) -> DiscoveryResult:
    if not params.get(metric, {}).get('enabled', True):
        return
    for key, data in section.items():
        if data.metric == metric:
            if debug.enabled():
                print(f"Metric: {metric}, item: {data.obj_name} discovered")
            yield Service(item=data.obj_name)


def check_oracle(item: str, params, section: Mapping[str, MetricData], metric: str, metric_def: dict) -> CheckResult:
    if debug.enabled():
        pprint(params)

    metric_num = metric[1:]  # 'm3000' -> '3000'
    key = item + ":" + metric_num

    if key not in section:
        yield Result(state=State.UNKNOWN, summary=f"No data received for {item}")
        return

    data = section[key]
    metric_params = params.get(metric, {})
    if not metric_params.get('enabled', True):
        if debug.enabled():
            print(f"The metric {metric} is disabled.")
        return

    state = calc_state(mname=metric, value=data.value, minmax=metric_params.get('type', 'MAX'), crit=metric_params.get('critical', 'NaN'), warn=metric_params.get('warning', 'NaN'))
    if debug.enabled():
        print(f"metric: {metric}, state: {state}")

    if state != State.OK:
        yield Result(
            state=state,
            summary=alert_description(data, metric_def),
            details=alert_description(data, metric_def),
        )
    else:
        yield Result(
            state=State.OK,
            summary=f"{data.obj_name} is healthy.",
        )

    if metric in metric_def and metric_def[metric]['counter']:
        yield Metric(metric_def[metric]['counter'], value=float(data.value))


def cluster_check_oracle(item: str, params, section: dict, metric: str, algorithm: str, metric_def: dict) -> CheckResult:
    if debug.enabled():
        pprint(section)

    metric_num = metric[1:]  # 'm3000' -> '3000'
    key = item + ":" + metric_num

    node_states = {}
    node_metric_data = {}
    for node_name, node_section in section.items():
        if key in node_section:
            data = node_section[key]
            if data.metric == metric:
                metric_params = params.get(metric, {})
                if metric_params.get('enabled', True):
                    node_states[node_name] = calc_state(mname=metric, value=data.value, minmax=metric_params.get('type', 'MAX'), crit=metric_params.get('critical', 'NaN'), warn=metric_params.get('warning', 'NaN'))
                    node_metric_data[node_name] = data

    if debug.enabled():
        pprint(node_states)
        pprint(node_metric_data)

    if node_states:
        yield Result(
            state = cluster_calc_state(node_states, algorithm),
            notice = cluster_alert_description(node_metric_data, metric_def),
        )
        mname = list(node_metric_data.values())[0].metric
        if metric_def[mname]['counter']:
            yield Metric(metric_def[mname]['counter'], cluster_metric_value(node_metric_data, algorithm, params[mname]['type']))
    else:
        yield Result(state=State.UNKNOWN, summary=f"No data received for {item}")
