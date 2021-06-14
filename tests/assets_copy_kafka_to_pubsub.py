#!/bin/python3

import yaml


# Edit tests/configs/yaml/hbs/pubsub/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/pubsub/config.yaml', 'r'))

data['services'][0]['type'] = 'pubsub'
del data['services'][0]['address']
data['services'][0]['actors'][9]['produce']['headers']['counter'] = "{{counter 'pubsubCounter'}}"

data['services'][2]['type'] = 'pubsub'
del data['services'][2]['address']

data['services'][3]['type'] = 'pubsub'
del data['services'][3]['address']

yaml.dump(data, open('tests/configs/yaml/hbs/pubsub/config.yaml', 'w'), sort_keys=False)


# Edit tests/configs/yaml/hbs/pubsub/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/pubsub/config_error.yaml', 'r'))

data['services'][0]['type'] = 'pubsub'
del data['services'][0]['address']

yaml.dump(data, open('tests/configs/yaml/hbs/pubsub/config_error.yaml', 'w'), sort_keys=False)
