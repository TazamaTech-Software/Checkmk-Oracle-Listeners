#!/usr/bin/env python3

from cmk.rulesets.v1 import Title, Help, Label
from cmk.rulesets.v1.form_specs import (
    BooleanChoice,
    DefaultValue,
    DictElement,
    Dictionary,
    List,
    String,
)

from cmk.rulesets.v1.rule_specs import (
    AgentConfig,
    CheckParameters,
    HostAndItemCondition,
    Topic,
)

from cmk_addons.plugins.oracle_listeners.oracle_listeners_metrics import METRIC_DEF
from cmk_addons.plugins.oracle_listeners.rulesets.ruleset_oracle_listeners_lib import metric_dict_elements


def _agent_parameter_form():
    return Dictionary(
        title=Title("Oracle Listeners Agent Plugin"),
        help_text=Help("Deploy the Oracle Listeners agent plugin to monitored hosts."),
        elements={
            "enabled": DictElement(
                parameter_form=BooleanChoice(
                    label=Label("Enable Oracle Listeners agent plugin"),
                    prefill=DefaultValue(True),
                ),
                required=True,
            ),
            "exclude": DictElement(
                parameter_form=List(
                    title=Title("Excluded listeners"),
                    help_text=Help(
                        "Listeners to exclude from monitoring. "
                        "Specify LSNRNAME to exclude by listener name across all Oracle homes, "
                        "or LSNRNAME:ORAHOME to exclude by name and specific Oracle home."
                    ),
                    element_template=String(
                        label=Label("Listener name or LSNRNAME:ORAHOME"),
                    ),
                ),
                required=False,
            ),
        },
    )


rule_spec_oracle_listeners_agent = AgentConfig(
    name="oracle_listeners",
    title=Title("Oracle Listeners"),
    topic=Topic.DATABASES,
    parameter_form=_agent_parameter_form,
)


def _parameter_form():
    return Dictionary(
        title=Title("Oracle Listeners Thresholds"),
        help_text=Help("Configure thresholds for specific Oracle Listener counters."),
        elements=metric_dict_elements(METRIC_DEF),
    )


rule_spec_oracle_listeners = CheckParameters(
    name="oracle_listeners_parameters",
    title=Title("Oracle Listeners Metrics"),
    topic=Topic.DATABASES,
    parameter_form=_parameter_form,
    condition=HostAndItemCondition(item_title=Title("Oracle Listeners Metrics")),
)
