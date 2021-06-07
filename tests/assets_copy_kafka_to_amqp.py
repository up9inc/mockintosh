#!/bin/python3

import yaml


# Edit tests/configs/yaml/hbs/amqp/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/amqp/config.yaml', 'r'))

data['services'][0]['type'] = 'amqp'
data['services'][0]['address'] = "{{env 'AMQP_ADDR' 'localhost:5672'}}"
data['services'][0]['actors'][9]['produce']['headers']['counter'] = "{{counter 'amqpCounter'}}"

data['services'][2]['type'] = 'amqp'
data['services'][2]['address'] = 'localhost:5673'

data['services'][3]['type'] = 'amqp'
data['services'][3]['address'] = 'localhost:5674'

yaml.dump(data, open('tests/configs/yaml/hbs/amqp/config.yaml', 'w'), sort_keys=False)


# Edit tests/configs/yaml/hbs/amqp/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/amqp/config_error.yaml', 'r'))

data['services'][0]['type'] = 'amqp'
data['services'][0]['address'] = "{{env 'AMQP_ADDR' 'localhost:5672'}}"

yaml.dump(data, open('tests/configs/yaml/hbs/amqp/config_error.yaml', 'w'), sort_keys=False)
