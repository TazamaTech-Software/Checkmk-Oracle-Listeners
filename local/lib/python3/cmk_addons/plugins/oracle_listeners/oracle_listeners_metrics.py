#!/usr/bin/env python3

METRIC_DEF = {
    'm3000': {'enabled': True, 'interval': '5m', 'type': 'MAX', 'critical': 'NaN', 'warning': '0.9', 'name': 'Oracle Listener',             'alert': "Listener '<LSNRNAME>' on Oracle home '<ORAHOME>' has error: '<ERROR>'.",              'counter': '', },
    'm3010': {'enabled': True, 'interval': '5m', 'type': 'MAX', 'critical': 'NaN', 'warning': '0.9', 'name': 'Oracle RAC SCAN Listener',    'alert': "SCAN Listener '<LSNRNAME>' on Oracle home '<ORAHOME>' has error: '<ERROR>'.",         'counter': '', },
    'm3020': {'enabled': True, 'interval': '5m', 'type': 'MAX', 'critical': 'NaN', 'warning': '0.9', 'name': 'Oracle Management Listener',  'alert': "Management Listener '<LSNRNAME>' on Oracle home '<ORAHOME>' has error: '<ERROR>'.",   'counter': '', },
}
