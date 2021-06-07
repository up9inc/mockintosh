#!/bin/python3

import yaml


# Edit tests/configs/yaml/hbs/redis/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/redis/config.yaml', 'r'))

data['services'][0]['type'] = 'redis'
data['services'][0]['address'] = "{{env 'REDIS_ADDR' 'localhost:6379'}}"
data['services'][0]['actors'][9]['produce']['headers']['counter'] = "{{counter 'redisCounter'}}"

data['services'][2]['type'] = 'redis'
data['services'][2]['address'] = 'localhost:6380'

data['services'][3]['type'] = 'redis'
data['services'][3]['address'] = 'localhost:6381'

yaml.dump(data, open('tests/configs/yaml/hbs/redis/config.yaml', 'w'), sort_keys=False)


# Edit tests/configs/yaml/hbs/redis/config.yaml
data = yaml.safe_load(open('tests/configs/yaml/hbs/redis/config_error.yaml', 'r'))

data['services'][0]['type'] = 'redis'
data['services'][0]['address'] = "{{env 'AMQP_ADDR' 'localhost:6379'}}"

yaml.dump(data, open('tests/configs/yaml/hbs/redis/config_error.yaml', 'w'), sort_keys=False)
