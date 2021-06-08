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


# Edit tests/configs/yaml/hbs/redis/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/redis/config.yaml', 'r'))

data['services'][0]['type'] = 'redis'
data['services'][0]['address'] = "{{env 'REDIS_ADDR' 'localhost:6379'}}"
data['services'][0]['actors'][9]['produce']['headers']['counter'] = "{{counter 'redisCounter'}}"
data['services'][0]['actors'][4]['produce']['value'] = "value5 and {{consumed.value}}"

data['services'][2]['type'] = 'redis'
data['services'][2]['address'] = 'localhost:6380'

data['services'][3]['type'] = 'redis'
data['services'][3]['address'] = 'localhost:6381'

remove_a_key(data, 'key')
remove_a_key(data, 'headers')

yaml.dump(data, open('tests/configs/yaml/hbs/redis/config.yaml', 'w'), sort_keys=False)


# Edit tests/configs/yaml/hbs/redis/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/redis/config_error.yaml', 'r'))

data['services'][0]['type'] = 'redis'
data['services'][0]['address'] = "{{env 'AMQP_ADDR' 'localhost:6379'}}"

remove_a_key(data, 'key')
remove_a_key(data, 'headers')

yaml.dump(data, open('tests/configs/yaml/hbs/redis/config_error.yaml', 'w'), sort_keys=False)
