#!/bin/python3

import yaml


# Edit tests/configs/yaml/hbs/mqtt/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/mqtt/config.yaml', 'r'))

data['services'][0]['type'] = 'mqtt'
data['services'][0]['address'] = "{{env 'MQTT_ADDR' 'localhost:1883'}}"
data['services'][0]['actors'][9]['produce']['headers']['counter'] = "{{counter 'mqttCounter'}}"

data['services'][2]['type'] = 'rabbitmq'
data['services'][2]['address'] = 'localhost:5673'

data['services'][3]['type'] = 'activemq'
data['services'][3]['address'] = 'localhost:5674'

yaml.dump(data, open('tests/configs/yaml/hbs/mqtt/config.yaml', 'w'), sort_keys=False)


# Edit tests/configs/yaml/hbs/mqtt/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/mqtt/config_error.yaml', 'r'))

data['services'][0]['type'] = 'mqtt'
data['services'][0]['address'] = "{{env 'MQTT_ADDR' 'localhost:1883'}}"

yaml.dump(data, open('tests/configs/yaml/hbs/mqtt/config_error.yaml', 'w'), sort_keys=False)
