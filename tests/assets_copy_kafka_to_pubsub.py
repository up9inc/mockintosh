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


# Edit tests/configs/yaml/hbs/pubsub/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/pubsub/config.yaml', 'r'))

data['services'][0]['type'] = 'pubsub'
del data['services'][0]['address']
data['services'][0]['actors'][9]['produce']['headers']['counter'] = "{{counter 'pubsubCounter'}}"

data['services'][2]['type'] = 'pubsub'
del data['services'][2]['address']

data['services'][3]['type'] = 'pubsub'
del data['services'][3]['address']

remove_a_key(data, 'key')
remove_a_key(data, 'headers')

yaml.dump(data, open('tests/configs/yaml/hbs/pubsub/config.yaml', 'w'), sort_keys=False)


# Edit tests/configs/yaml/hbs/pubsub/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/pubsub/config_error.yaml', 'r'))

data['services'][0]['type'] = 'pubsub'
del data['services'][0]['address']

remove_a_key(data, 'key')
remove_a_key(data, 'headers')

yaml.dump(data, open('tests/configs/yaml/hbs/pubsub/config_error.yaml', 'w'), sort_keys=False)
