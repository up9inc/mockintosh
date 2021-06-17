#!/bin/python3

import yaml


# Edit tests/configs/yaml/hbs/gpubsub/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/gpubsub/config.yaml', 'r'))

data['services'][0]['type'] = 'gpubsub'
del data['services'][0]['address']
data['services'][0]['actors'][9]['produce']['headers']['counter'] = "{{counter 'gpubsubCounter'}}"

data['services'].pop()
data['services'].pop()

yaml.dump(data, open('tests/configs/yaml/hbs/gpubsub/config.yaml', 'w'), sort_keys=False)


# Edit tests/configs/yaml/hbs/gpubsub/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/gpubsub/config_error.yaml', 'r'))

data['services'][0]['type'] = 'gpubsub'
del data['services'][0]['address']

yaml.dump(data, open('tests/configs/yaml/hbs/gpubsub/config_error.yaml', 'w'), sort_keys=False)
