#!/usr/bin/env python3

from cmk.rulesets.v1 import Label, Title, Help
from cmk.rulesets.v1.form_specs import (
    BooleanChoice,
    DefaultValue,
    DictGroup,
    DictElement,
    Dictionary,
    String,
    Float,
    Integer,
    List,
    LevelDirection,
    SimpleLevels,
    SingleChoice,
    SingleChoiceElement,
    validators,
    FieldSize,
    FixedValue,
)

def metric_dict_elements(metric_def: dict):
    metrics = {}
    for metric in metric_def:
        metrics[metric] = DictElement(
                parameter_form = Dictionary(
                    title = Title(metric_def[metric]['name']),
                    elements = {
                        'enabled': DictElement(
                                        parameter_form = BooleanChoice(
                                            label = Label('Enabled'),
                                            prefill = DefaultValue(metric_def[metric]['enabled']),
                                        ),
                                        required = True,
                                        group = DictGroup(),
                                    ),
                        'critical': DictElement(
                                        parameter_form = String(
                                            label = Label('Critical:'),
                                            field_size = FieldSize.SMALL,
                                            prefill = DefaultValue(metric_def[metric]['critical']),
                                            custom_validate = (validators.MatchRegex(regex='([-]?([0-9]+[.])?[0-9]+|NaN)'),),
                                        ),
                                        required=True,
                                        group = DictGroup(),
                                    ),
                        'warning': DictElement(
                                        parameter_form = String(
                                            label = Label('Warning: '),
                                            field_size = FieldSize.SMALL,
                                            prefill = DefaultValue(metric_def[metric]['warning']),
                                            custom_validate = (validators.MatchRegex(regex='([-]?([0-9]+[.])?[0-9]+|NaN)'),),
                                        ),
                                        required = True,
                                        group = DictGroup(),
                                    ),
                        'type': DictElement(
                                        parameter_form = FixedValue(
                                            label = Label('Threshold type: ' + metric_def[metric]['type']),
                                            value = str(metric_def[metric]['type']),
                                        ),
                                        required = True,
                                        group = DictGroup(),
                                ),

                    },
                ),
                required = True,
            )
    return metrics
