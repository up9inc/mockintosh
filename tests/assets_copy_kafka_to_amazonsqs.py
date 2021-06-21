#!/bin/python3

import yaml


# Edit tests/configs/yaml/hbs/amazonsqs/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/amazonsqs/config.yaml', 'r'))

data['services'][0]['type'] = 'amazonsqs'
data['services'][0]['address'] = "{{env 'AMAZONSQS_ADDR' 'localhost:9324'}}"
data['services'][0]['actors'][9]['produce']['headers']['counter'] = "{{counter 'amazonsqsCounter'}}"

data['services'][2]['type'] = 'rabbitmq'
data['services'][2]['address'] = 'localhost:9325'

data['services'][3]['type'] = 'activemq'
data['services'][3]['address'] = 'localhost:9326'

yaml.dump(data, open('tests/configs/yaml/hbs/amazonsqs/config.yaml', 'w'), sort_keys=False)


# Edit tests/configs/yaml/hbs/amazonsqs/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/amazonsqs/config_error.yaml', 'r'))

data['services'][0]['type'] = 'amazonsqs'
data['services'][0]['address'] = "{{env 'AMAZONSQS_ADDR' 'localhost:9324'}}"

yaml.dump(data, open('tests/configs/yaml/hbs/amazonsqs/config_error.yaml', 'w'), sort_keys=False)
