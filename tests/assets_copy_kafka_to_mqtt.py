#!/bin/python3

import yaml


def remove_a_key(d, remove_key) -> dict:
    if isinstance(d, dict):
        for key in list(d.keys()):
            if key == remove_key:
                del d[key]
            else:
                remove_a_key(d[key], remove_key)
    elif isinstance(d, list):
        for x in d:
            remove_a_key(x, remove_key)


# Edit tests/configs/yaml/hbs/mqtt/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/mqtt/config.yaml', 'r'))

data['services'][0]['type'] = 'mqtt'
data['services'][0]['address'] = "{{env 'MQTT_ADDR' 'localhost:1883'}}"
data['services'][0]['actors'][9]['produce']['headers']['counter'] = "{{counter 'mqttCounter'}}"
data['services'][0]['actors'][4]['produce']['value'] = "value5 and {{consumed.value}}"

data['services'][2]['type'] = 'mqtt'
data['services'][2]['address'] = 'localhost:5673'

data['services'][3]['type'] = 'mqtt'
data['services'][3]['address'] = 'localhost:5674'

remove_a_key(data, 'key')
remove_a_key(data, 'headers')

yaml.dump(data, open('tests/configs/yaml/hbs/mqtt/config.yaml', 'w'), sort_keys=False)


# Edit tests/configs/yaml/hbs/mqtt/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/mqtt/config_error.yaml', 'r'))

data['services'][0]['type'] = 'mqtt'
data['services'][0]['address'] = "{{env 'MQTT_ADDR' 'localhost:1883'}}"

remove_a_key(data, 'key')
remove_a_key(data, 'headers')

yaml.dump(data, open('tests/configs/yaml/hbs/mqtt/config_error.yaml', 'w'), sort_keys=False)
