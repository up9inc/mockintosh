#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: Contains classes that tests mock server's asynchronous features.
"""

import sys
import os
import time
import json
import threading
import subprocess
from typing import (
    Union
)

import httpx
import yaml
from jsonschema.validators import validate as jsonschema_validate

from mockintosh.constants import PROGRAM, PYBARS, JINJA
from mockintosh import start_render_queue
from mockintosh.services.asynchronous.kafka import (  # noqa: F401
    KafkaService,
    KafkaActor,
    KafkaConsumer,
    KafkaConsumerGroup,
    KafkaProducer,
    KafkaProducerPayloadList,
    KafkaProducerPayload,
    _create_topic as kafka_create_topic,
    build_single_payload_producer as kafka_build_single_payload_producer
)
from mockintosh.services.asynchronous.amqp import (  # noqa: F401
    AmqpService,
    AmqpActor,
    AmqpConsumer,
    AmqpConsumerGroup,
    AmqpProducer,
    AmqpProducerPayloadList,
    AmqpProducerPayload,
    _create_topic as amqp_create_topic,
    build_single_payload_producer as amqp_build_single_payload_producer
)
from mockintosh.services.asynchronous.redis import (  # noqa: F401
    RedisService,
    RedisActor,
    RedisConsumer,
    RedisConsumerGroup,
    RedisProducer,
    RedisProducerPayloadList,
    RedisProducerPayload,
    _create_topic as redis_create_topic,
    build_single_payload_producer as redis_build_single_payload_producer
)
from utilities import (
    DefinitionMockForAsync,
    get_config_path,
    is_valid_uuid
)

MGMT = os.environ.get('MGMT', 'https://localhost:8000')

KAFKA_ADDR = os.environ.get('KAFKA_ADDR', 'localhost:9092')
AMQP_ADDR = os.environ.get('AMQP_ADDR', 'localhost:5672')
REDIS_ADDR = os.environ.get('REDIS_ADDR', 'localhost:6379')
ASYNC_ADDR = {
    'kafka': KAFKA_ADDR,
    'amqp': AMQP_ADDR,
    'redis': REDIS_ADDR
}
ASYNC_CONSUME_TIMEOUT = os.environ.get('ASYNC_CONSUME_TIMEOUT', 120)
ASYNC_CONSUME_WAIT = os.environ.get('ASYNC_CONSUME_WAIT', 0.5)

HAR_JSON_SCHEMA = {"$ref": "https://raw.githubusercontent.com/undera/har-jsonschema/master/har-schema.json"}

should_cov = os.environ.get('COVERAGE_PROCESS_START', False)
async_service_type = None


class AsyncBase():

    mock_server_process = None

    @classmethod
    def setup_class(cls):
        global async_service_type

        config = 'configs/yaml/hbs/%s/config.yaml' % async_service_type

        # Create the Async topics/queues
        for topic in (
            'topic1',
            'topic4',
            'topic5',
            'topic6',
            'topic7',
            'topic8',
            'topic9',
            'templated-producer',
            'topic10',
            'topic11',
            'topic12',
            'topic13',
            'topic14',
            'topic15',
            'topic16',
            'topic17',
            'topic18',
            'topic19',
            'topic20',
            'binary-topic',
            'chain1-step1',
            'chain1-step2'
        ):
            getattr(sys.modules[__name__], '%s_create_topic' % async_service_type)(ASYNC_ADDR[async_service_type], topic)

        time.sleep(ASYNC_CONSUME_TIMEOUT / 20)

        cmd = '%s %s' % (PROGRAM, get_config_path(config))
        if should_cov:
            cmd = 'coverage run --parallel -m %s' % cmd
        this_env = os.environ.copy()
        AsyncBase.mock_server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True,
            env=this_env
        )
        time.sleep(ASYNC_CONSUME_TIMEOUT / 20)

        getattr(sys.modules[__name__], '%s_create_topic' % async_service_type)(ASYNC_ADDR[async_service_type], 'topic2')

        resp = httpx.post(MGMT + '/traffic-log', data={"enable": True}, verify=False)
        assert 204 == resp.status_code

    @classmethod
    def teardown_class(cls):
        AsyncBase.mock_server_process.kill()
        name = PROGRAM
        if should_cov:
            name = 'coverage'
        os.system('killall -2 %s' % name)

    def assert_consumer_log(self, data: dict, key: Union[str, None], value: str, headers: dict, invert: bool = False):
        global async_service_type

        if async_service_type != 'redis' and key is not None:
            criteria = any(any(header['name'] == 'X-%s-Message-Key' % PROGRAM.capitalize() and header['value'] == key for header in entry['response']['headers']) for entry in data['log']['entries'])
            if invert:
                assert not criteria
            else:
                assert criteria
        criteria = any(entry['response']['content']['text'] == value for entry in data['log']['entries'])
        if invert:
            assert not criteria
        else:
            assert criteria

        if async_service_type != 'redis':
            for n, v in headers.items():
                criteria = any(any(header['name'] == n.title() and header['value'] == v for header in entry['response']['headers']) for entry in data['log']['entries'])
                if invert:
                    assert not criteria
                else:
                    assert criteria

    def assert_async_consume(self, callback, *args):
        start = time.time()
        while True:
            try:
                callback(*args)
            except AssertionError:
                time.sleep(ASYNC_CONSUME_WAIT)
                if time.time() - start > ASYNC_CONSUME_TIMEOUT:
                    raise
                else:
                    continue
            break

    def test_get_async(self):
        global async_service_type

        for _format in ('json', 'yaml'):
            resp = httpx.get(MGMT + '/async?format=%s' % _format, verify=False)
            assert 200 == resp.status_code
            if _format == 'json':
                assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
            elif _format == 'yaml':
                assert resp.headers['Content-Type'] == 'application/x-yaml'
            data = yaml.safe_load(resp.text)

            producers = data['producers']
            consumers = data['consumers']
            assert len(producers) == 23
            assert len(consumers) == 16

            assert producers[0]['type'] == async_service_type
            assert producers[0]['name'] is None
            assert producers[0]['index'] == 0
            assert producers[0]['queue'] == 'topic1'
            assert producers[0]['producedMessages'] == 0
            assert producers[0]['lastProduced'] is None

            assert producers[3]['type'] == async_service_type
            assert producers[3]['name'] == 'actor6'
            assert producers[3]['index'] == 3
            assert producers[3]['queue'] == 'topic6'

            assert consumers[0]['type'] == async_service_type
            assert consumers[0]['name'] is None
            assert consumers[0]['index'] == 0
            assert consumers[0]['queue'] == 'topic2'
            assert consumers[0]['captured'] == 0
            assert consumers[0]['consumedMessages'] == 0
            assert consumers[0]['lastConsumed'] is None

            assert consumers[3]['type'] == async_service_type
            assert consumers[3]['name'] == 'actor9'
            assert consumers[3]['index'] == 3
            assert consumers[3]['queue'] == 'topic9'

    def assert_get_async_chain(self, value, headers):
        resp = httpx.get(MGMT + '/async/consumers/chain1-validating', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        self.assert_consumer_log(data, None, '%s-val' % value, headers)

    def test_get_async_chain(self):
        value = '123456'
        headers = {
            'Captured-Key': '%s-key' % value,
            'Captured-Val': '%s-val' % value,
            'Captured-Hdr': '%s-hdr' % value
        }

        resp = httpx.post(MGMT + '/async/producers/chain1-on-demand', verify=False)
        assert 202 == resp.status_code

        self.assert_async_consume(
            self.assert_get_async_chain,
            value,
            headers
        )

    def assert_get_async_consume(
        self,
        key,
        value,
        headers,
        not_key,
        not_value,
        not_headers1,
        not_headers2
    ):
        resp = httpx.get(MGMT + '/async/consumers/0', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        self.assert_consumer_log(data, key, value, headers)
        self.assert_consumer_log(data, not_key, not_value, not_headers1, invert=True)
        self.assert_consumer_log(data, not_key, not_value, not_headers2, invert=True)

    def test_get_async_consume(self):
        global async_service_type

        key = 'key2'
        value = """
        {"somekey": "value"}
"""
        headers = {'hdr2': 'val2'}

        not_key = 'not_key2'
        not_value = """
        {"some_other_key": "value"}
"""
        not_headers1 = {'hdr2': 'not_val2'}
        not_headers2 = {'not_hdr2': 'val2'}

        value_json_decode_error = 'JSON Decode Error'

        queue, job = start_render_queue()
        async_service = getattr(sys.modules[__name__], '%sService' % async_service_type.capitalize())(
            ASYNC_ADDR[async_service_type],
            definition=DefinitionMockForAsync(None, PYBARS, queue)
        )
        async_actor = getattr(sys.modules[__name__], '%sActor' % async_service_type.capitalize())(0)
        async_service.add_actor(async_actor)
        async_producer = getattr(sys.modules[__name__], '%s_build_single_payload_producer' % async_service_type)(
            'topic2',
            value,
            key=key,
            headers=headers
        )
        async_actor.set_producer(async_producer)
        async_producer.produce()
        time.sleep(1)
        async_producer.produce()
        time.sleep(1)

        async_producer = getattr(sys.modules[__name__], '%s_build_single_payload_producer' % async_service_type)(
            'topic2',
            value,
            key=not_key,
            headers=headers
        )
        async_actor.set_producer(async_producer)
        async_producer.produce()
        time.sleep(1)

        async_producer = getattr(sys.modules[__name__], '%s_build_single_payload_producer' % async_service_type)(
            'topic2',
            not_value,
            key=key,
            headers=headers
        )
        async_actor.set_producer(async_producer)
        async_producer.produce()
        time.sleep(1)

        async_producer = getattr(sys.modules[__name__], '%s_build_single_payload_producer' % async_service_type)(
            'topic2',
            value_json_decode_error,
            key=key,
            headers=headers
        )
        async_actor.set_producer(async_producer)
        async_producer.produce()
        time.sleep(1)

        async_producer = getattr(sys.modules[__name__], '%s_build_single_payload_producer' % async_service_type)(
            'topic2',
            value,
            key=key,
            headers=not_headers1
        )
        async_actor.set_producer(async_producer)
        async_producer.produce()
        time.sleep(1)

        async_producer = getattr(sys.modules[__name__], '%s_build_single_payload_producer' % async_service_type)(
            'topic2',
            value,
            key=key,
            headers=not_headers2
        )
        async_actor.set_producer(async_producer)
        async_producer.produce()
        time.sleep(1)

        self.assert_async_consume(
            self.assert_get_async_consume,
            key,
            value,
            headers,
            not_key,
            not_value,
            not_headers1,
            not_headers2
        )

        resp = httpx.get(MGMT + '/async', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        consumers = data['consumers']
        assert consumers[0]['captured'] == 1
        assert consumers[0]['consumedMessages'] == 2 if async_service_type != 'redis' else 3

        job.kill()

    def assert_get_async_produce_consume_loop(self, key, value, headers):
        resp = httpx.get(MGMT + '/async/consumers/1', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        self.assert_consumer_log(data, key, value, headers)

    def test_get_async_produce_consume_loop(self):
        key = 'key3'
        value = 'value3'
        headers = {
            'hdr3': 'val3',
            'global-hdr1': 'globalval1',
            'global-hdr2': 'globalval2'
        }

        self.assert_async_consume(
            self.assert_get_async_produce_consume_loop,
            key,
            value,
            headers
        )

    def assert_get_async_consume_no_key(self, key, value, headers):
        resp = httpx.get(MGMT + '/async/consumers/4', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        self.assert_consumer_log(data, key, value, headers)

    def test_get_async_consume_no_key(self):
        global async_service_type

        key = None
        value = 'value10'
        headers = {}

        queue, job = start_render_queue()
        async_service = getattr(sys.modules[__name__], '%sService' % async_service_type.capitalize())(
            ASYNC_ADDR[async_service_type],
            definition=DefinitionMockForAsync(None, JINJA, queue)
        )
        async_actor = getattr(sys.modules[__name__], '%sActor' % async_service_type.capitalize())(0)
        async_service.add_actor(async_actor)
        async_producer = getattr(sys.modules[__name__], '%s_build_single_payload_producer' % async_service_type)(
            'topic10',
            value,
            key=key,
            headers=headers
        )
        async_actor.set_producer(async_producer)
        async_producer.produce()

        self.assert_async_consume(
            self.assert_get_async_consume_no_key,
            key,
            value,
            headers
        )

        job.kill()

    def assert_get_async_consume_capture_limit_part1(self, value10_1, value10_2):
        resp = httpx.get(MGMT + '/async/consumers/4', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        assert not any(entry['response']['content']['text'] == value10_1 for entry in data['log']['entries'])
        assert any(entry['response']['content']['text'] == value10_2 for entry in data['log']['entries'])

    def assert_get_async_consume_capture_limit_part2(self, value11_1, value11_2):
        resp = httpx.get(MGMT + '/async/consumers/capture-limit', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        assert any(entry['response']['content']['text'] == value11_1 for entry in data['log']['entries'])
        assert any(entry['response']['content']['text'] == value11_2 for entry in data['log']['entries'])

    def test_get_async_consume_capture_limit(self):
        global async_service_type

        topic10 = 'topic10'
        value10_1 = 'value10_1'
        value10_2 = 'value10_2'

        topic11 = 'topic11'
        value11_1 = 'value11_1'
        value11_2 = 'value11_2'

        queue, job = start_render_queue()
        async_service = getattr(sys.modules[__name__], '%sService' % async_service_type.capitalize())(
            ASYNC_ADDR[async_service_type],
            definition=DefinitionMockForAsync(None, PYBARS, queue)
        )
        async_actor = getattr(sys.modules[__name__], '%sActor' % async_service_type.capitalize())(0)
        async_service.add_actor(async_actor)

        # topic10 START
        async_producer = getattr(sys.modules[__name__], '%s_build_single_payload_producer' % async_service_type)(
            topic10,
            value10_1
        )
        async_actor.set_producer(async_producer)
        async_producer.produce()

        async_producer = getattr(sys.modules[__name__], '%s_build_single_payload_producer' % async_service_type)(
            topic10,
            value10_2
        )
        async_actor.set_producer(async_producer)
        async_producer.produce()

        self.assert_async_consume(
            self.assert_get_async_consume_capture_limit_part1,
            value10_1,
            value10_2
        )
        # topic10 END

        # topic11 START
        async_producer = getattr(sys.modules[__name__], '%s_build_single_payload_producer' % async_service_type)(
            topic11,
            value11_1
        )
        async_actor.set_producer(async_producer)
        async_producer.produce()

        async_producer = getattr(sys.modules[__name__], '%s_build_single_payload_producer' % async_service_type)(
            topic11,
            value11_2
        )
        async_actor.set_producer(async_producer)
        async_producer.produce()

        self.assert_async_consume(
            self.assert_get_async_consume_capture_limit_part2,
            value11_1,
            value11_2
        )
        # topic11 END

        # DELETE endpoint
        resp = httpx.delete(MGMT + '/async/consumers/4', verify=False)
        assert 204 == resp.status_code
        resp = httpx.get(MGMT + '/async/consumers/4', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert not data['log']['entries']

        resp = httpx.delete(MGMT + '/async/consumers/capture-limit', verify=False)
        assert 204 == resp.status_code
        resp = httpx.get(MGMT + '/async/consumers/capture-limit', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert not data['log']['entries']

        job.kill()

    def test_get_async_bad_requests(self):
        resp = httpx.get(MGMT + '/async/consumers/99', verify=False)
        assert 400 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'Invalid consumer index!'

        actor_name = 'not-existing-actor'
        resp = httpx.get(MGMT + '/async/consumers/%s' % actor_name, verify=False)
        assert 400 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'No consumer actor is found for: %r' % actor_name

    def assert_post_async_produce(self, async_consumer, key, value, headers):
        global async_service_type

        if async_service_type == 'redis':
            assert any(row[1] == value for row in async_consumer.log)
        else:
            assert any(row[0] == key and row[1] == value and row[2] == headers for row in async_consumer.log)

    def test_post_async_produce(self):
        global async_service_type

        key = 'key1'
        value = 'value1'
        headers = {
            'hdr1': 'val1',
            'global-hdr1': 'globalval1',
            'global-hdr2': 'globalval2'
        }

        queue, job = start_render_queue()
        async_service = getattr(sys.modules[__name__], '%sService' % async_service_type.capitalize())(
            ASYNC_ADDR[async_service_type],
            definition=DefinitionMockForAsync(None, PYBARS, queue)
        )
        async_actor = getattr(sys.modules[__name__], '%sActor' % async_service_type.capitalize())(0)
        async_service.add_actor(async_actor)
        async_consumer = getattr(sys.modules[__name__], '%sConsumer' % async_service_type.capitalize())('topic1', enable_topic_creation=True)
        async_actor.set_consumer(async_consumer)
        async_consumer_group = getattr(sys.modules[__name__], '%sConsumerGroup' % async_service_type.capitalize())()
        async_consumer_group.add_consumer(async_consumer)
        t = threading.Thread(target=async_consumer_group.consume, args=(), kwargs={})
        t.daemon = True
        t.start()

        resp = httpx.post(MGMT + '/async/producers/0', verify=False)
        assert 202 == resp.status_code

        self.assert_async_consume(
            self.assert_post_async_produce,
            async_consumer,
            key,
            value,
            headers
        )

        async_consumer_group._stop()
        t.join()
        job.kill()

    def test_post_async_binary_produce(self):
        resp = httpx.post(MGMT + '/async/producers/Binary%20Producer', verify=False)
        assert 202 == resp.status_code

    def assert_post_async_produce_by_actor_name(self, async_consumer, key, value, headers):
        global async_service_type

        if async_service_type == 'redis':
            assert any(row[1] == value for row in async_consumer.log)
        else:
            assert any(row[0] == key and row[1] == value and row[2] == headers for row in async_consumer.log)

    def test_post_async_produce_by_actor_name(self):
        global async_service_type

        key = None
        value = 'value6'
        headers = {
            'global-hdr1': 'globalval1',
            'global-hdr2': 'globalval2'
        }

        queue, job = start_render_queue()
        async_service = getattr(sys.modules[__name__], '%sService' % async_service_type.capitalize())(
            ASYNC_ADDR[async_service_type],
            definition=DefinitionMockForAsync(None, JINJA, queue)
        )
        async_actor = getattr(sys.modules[__name__], '%sActor' % async_service_type.capitalize())(0)
        async_service.add_actor(async_actor)
        async_consumer = getattr(sys.modules[__name__], '%sConsumer' % async_service_type.capitalize())('topic6')
        async_actor.set_consumer(async_consumer)
        async_consumer_group = getattr(sys.modules[__name__], '%sConsumerGroup' % async_service_type.capitalize())()
        async_consumer_group.add_consumer(async_consumer)
        t = threading.Thread(target=async_consumer_group.consume, args=(), kwargs={})
        t.daemon = True
        t.start()

        resp = httpx.post(MGMT + '/async/producers/actor6', verify=False)
        assert 202 == resp.status_code

        self.assert_async_consume(
            self.assert_post_async_produce_by_actor_name,
            async_consumer,
            key,
            value,
            headers
        )

        async_consumer_group._stop()
        t.join()
        job.kill()

    def assert_post_async_reactive_consumer(
        self,
        async_consumer,
        consumer_key,
        consumer_value,
        consumer_headers,
        producer_key,
        producer_value,
        producer_headers
    ):
        global async_service_type

        if async_service_type == 'redis':
            assert any(
                (row[1] == '%s and %s' % (
                    consumer_value,
                    producer_value
                ))
                for row in async_consumer.log
            )
        else:
            assert any(
                (row[0] == consumer_key)
                and  # noqa: W504, W503
                (row[1] == '%s and %s %s %s' % (
                    consumer_value,
                    producer_key,
                    producer_value,
                    producer_headers['hdr4']
                ))
                and  # noqa: W504, W503
                (row[2] == consumer_headers)
                for row in async_consumer.log
            )

    def test_post_async_reactive_consumer(self):
        global async_service_type

        producer_topic = 'topic4'
        producer_key = 'key4'
        producer_value = """
        {"somekey": "value"}
"""
        producer_headers = {'hdr4': 'val4'}

        consumer_topic = 'topic5'
        consumer_key = 'key5'
        consumer_value = 'value5'
        consumer_headers = {
            'hdr5': 'val5',
            'global-hdr1': 'globalval1',
            'global-hdr2': 'globalval2'
        }

        queue, job = start_render_queue()
        async_service = getattr(sys.modules[__name__], '%sService' % async_service_type.capitalize())(
            ASYNC_ADDR[async_service_type],
            definition=DefinitionMockForAsync(None, PYBARS, queue)
        )
        async_actor = getattr(sys.modules[__name__], '%sActor' % async_service_type.capitalize())(0)
        async_service.add_actor(async_actor)
        async_consumer = getattr(sys.modules[__name__], '%sConsumer' % async_service_type.capitalize())(consumer_topic)
        async_actor.set_consumer(async_consumer)
        async_consumer_group = getattr(sys.modules[__name__], '%sConsumerGroup' % async_service_type.capitalize())()
        async_consumer_group.add_consumer(async_consumer)
        t = threading.Thread(target=async_consumer_group.consume, args=(), kwargs={})
        t.daemon = True
        t.start()

        async_service = getattr(sys.modules[__name__], '%sService' % async_service_type.capitalize())(
            ASYNC_ADDR[async_service_type],
            definition=DefinitionMockForAsync(None, PYBARS, queue)
        )
        async_actor = getattr(sys.modules[__name__], '%sActor' % async_service_type.capitalize())(0)
        async_service.add_actor(async_actor)
        async_producer = getattr(sys.modules[__name__], '%s_build_single_payload_producer' % async_service_type)(
            producer_topic,
            producer_value,
            key=producer_key,
            headers=producer_headers
        )
        async_actor.set_producer(async_producer)
        async_producer.produce()

        self.assert_async_consume(
            self.assert_post_async_reactive_consumer,
            async_consumer,
            consumer_key,
            consumer_value,
            consumer_headers,
            producer_key,
            producer_value,
            producer_headers
        )

        async_consumer_group._stop()
        t.join()
        job.kill()

    def test_post_async_bad_requests(self):
        actor99 = 'actor99'
        resp = httpx.post(MGMT + '/async/producers/%s' % actor99, verify=False)
        assert 400 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'No producer actor is found for: %r' % actor99

        resp = httpx.post(MGMT + '/async/producers/99', verify=False)
        assert 400 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'Invalid producer index!'

    def assert_post_async_producer_templated(self, async_consumer):
        global async_service_type

        for i in range(2):
            if async_service_type == 'redis':
                assert any(
                    (row[1][0].isupper())
                    for row in async_consumer.log
                )
            else:
                assert any(
                    (row[0].startswith('prefix-') and is_valid_uuid(row[0][7:]))
                    and  # noqa: W504, W503
                    (row[1][0].isupper())
                    and  # noqa: W504, W503
                    (row[2]['name'] == 'templated')
                    and  # noqa: W504, W503
                    (row[2]['constant'] == 'constant-value')
                    and  # noqa: W504, W503
                    (len(row[2]['timestamp']) == 10 and row[2]['timestamp'].isnumeric())
                    and  # noqa: W504, W503
                    (int(row[2]['counter']) == i + 1)
                    and  # noqa: W504, W503
                    (int(row[2]['fromFile'][10:11]) < 10 and int(row[2]['fromFile'][28:30]) < 100)
                    for row in async_consumer.log
                )

    def test_post_async_producer_templated(self):
        global async_service_type

        queue, job = start_render_queue()
        async_service = getattr(sys.modules[__name__], '%sService' % async_service_type.capitalize())(
            ASYNC_ADDR[async_service_type],
            definition=DefinitionMockForAsync(None, PYBARS, queue)
        )
        async_actor = getattr(sys.modules[__name__], '%sActor' % async_service_type.capitalize())(0)
        async_service.add_actor(async_actor)
        async_consumer = getattr(sys.modules[__name__], '%sConsumer' % async_service_type.capitalize())('templated-producer', capture_limit=2)
        async_actor.set_consumer(async_consumer)
        async_consumer_group = getattr(sys.modules[__name__], '%sConsumerGroup' % async_service_type.capitalize())()
        async_consumer_group.add_consumer(async_consumer)
        t = threading.Thread(target=async_consumer_group.consume, args=(), kwargs={})
        t.daemon = True
        t.start()

        for _ in range(2):
            resp = httpx.post(MGMT + '/async/producers/templated-producer', verify=False)
            assert 202 == resp.status_code

        self.assert_async_consume(
            self.assert_post_async_producer_templated,
            async_consumer
        )

        async_consumer_group._stop()
        t.join()
        job.kill()

    def test_async_producer_list_has_no_payloads_matching_tags(self):
        global async_service_type

        queue, job = start_render_queue()
        async_service = getattr(sys.modules[__name__], '%sService' % async_service_type.capitalize())(
            'localhost:%s' % ASYNC_ADDR[async_service_type].split(':')[1],
            definition=DefinitionMockForAsync(None, PYBARS, queue)
        )
        async_actor = getattr(sys.modules[__name__], '%sActor' % async_service_type.capitalize())(0)
        async_service.add_actor(async_actor)
        async_producer = getattr(sys.modules[__name__], '%s_build_single_payload_producer' % async_service_type)(
            'topic12',
            'value12-3',
            key='key12-3',
            headers={'hdr12-3': 'val12-3'},
            tag='async-tag12-3'
        )
        async_actor.set_producer(async_producer)
        async_producer.produce()
        job.kill()

    def assert_post_async_multiproducer_part1(self):
        resp = httpx.get(MGMT + '/async/consumers/consumer-for-multiproducer', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        for key, value, headers in [
            ('key12-1', 'value12-1', {'hdr12-1': 'val12-1'}),
            ('key12-2', 'value12-2', {'hdr12-2': 'val12-2'}),
        ]:
            self.assert_consumer_log(data, key, value, headers)

        assert len(data['log']['entries']) == 3

    def assert_post_async_multiproducer_part2(self):
        resp = httpx.get(MGMT + '/async/consumers/consumer-for-multiproducer', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        for key, value, headers in [
            ('key12-3', 'value12-3', {'hdr12-3': 'val12-3'}),
        ]:
            self.assert_consumer_log(data, key, value, headers)

        assert len(data['log']['entries']) == 5

    def assert_post_async_multiproducer_part3(self):
        resp = httpx.get(MGMT + '/async/consumers/consumer-for-multiproducer', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        for key, value, headers in [
            ('key12-4', 'value12-4', {'hdr12-4': 'val12-4'}),
        ]:
            self.assert_consumer_log(data, key, value, headers, invert=True)

        assert len(data['log']['entries']) == 6

    def test_post_async_multiproducer(self):
        for _ in range(3):
            resp = httpx.post(MGMT + '/async/producers/multiproducer', verify=False)
            assert 202 == resp.status_code

        self.assert_async_consume(self.assert_post_async_multiproducer_part1)

        resp = httpx.post(MGMT + '/tag', data="async-tag12-3", verify=False)
        assert 204 == resp.status_code

        for _ in range(2):
            resp = httpx.post(MGMT + '/async/producers/multiproducer', verify=False)
            assert 202 == resp.status_code

        self.assert_async_consume(self.assert_post_async_multiproducer_part2)

        resp = httpx.post(MGMT + '/async/producers/multiproducer', verify=False)
        assert 202 == resp.status_code

        self.assert_async_consume(self.assert_post_async_multiproducer_part3)

        resp = httpx.get(MGMT + '/tag', verify=False)
        assert 200 == resp.status_code
        data = resp.json()
        assert data == {'tags': ['async-tag12-3']}

        resp = httpx.post(MGMT + '/reset-iterators', verify=False)
        assert 204 == resp.status_code

    def test_post_async_multiproducer_no_payloads_matching_tags(self):
        resp = httpx.post(MGMT + '/tag', data="", verify=False)
        assert 204 == resp.status_code

        resp = httpx.post(MGMT + '/async/producers/multiproducer-error', verify=False)
        assert 410 == resp.status_code

        resp = httpx.post(MGMT + '/async/producers/11', verify=False)
        assert 410 == resp.status_code

    def test_post_async_multiproducer_nonlooped(self):
        for _ in range(2):
            resp = httpx.post(MGMT + '/async/producers/multiproducer-nonlooped', verify=False)
            assert 202 == resp.status_code

        resp = httpx.post(MGMT + '/async/producers/multiproducer-nonlooped', verify=False)
        assert 410 == resp.status_code

    def assert_post_async_dataset_part1(self):
        resp = httpx.get(MGMT + '/async/consumers/consumer-for-dataset', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        for key, value, headers in [
            ('key13', 'dset: 3.1', {'hdr13': 'val13'}),
            ('key13', 'dset: 3.2', {'hdr13': 'val13'}),
            ('key13', 'dset: 3.3', {'hdr13': 'val13'}),
        ]:
            self.assert_consumer_log(data, key, value, headers)

        assert len(data['log']['entries']) == 3

    def assert_post_async_dataset_part2(self):
        resp = httpx.get(MGMT + '/async/consumers/consumer-for-dataset', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        for key, value, headers in [
            ('key13', 'dset: 1.1', {'hdr13': 'val13'}),
            ('key13', 'dset: 1.2', {'hdr13': 'val13'}),
        ]:
            self.assert_consumer_log(data, key, value, headers)

        assert len(data['log']['entries']) == 9

    def assert_post_async_dataset_part3(self):
        resp = httpx.get(MGMT + '/async/consumers/consumer-for-dataset', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        for key, value, headers in [
            ('key13', 'dset: 2.1', {'hdr13': 'val13'}),
            ('key13', 'dset: 2.2', {'hdr13': 'val13'}),
        ]:
            self.assert_consumer_log(data, key, value, headers)

        assert len(data['log']['entries']) == 13

    def test_post_async_dataset(self):
        for _ in range(3):
            resp = httpx.post(MGMT + '/async/producers/dataset', verify=False)
            assert 202 == resp.status_code

        self.assert_async_consume(self.assert_post_async_dataset_part1)

        resp = httpx.post(MGMT + '/tag', data="first", verify=False)
        assert 204 == resp.status_code

        for _ in range(6):
            resp = httpx.post(MGMT + '/async/producers/dataset', verify=False)
            assert 202 == resp.status_code

        self.assert_async_consume(self.assert_post_async_dataset_part2)

        resp = httpx.post(MGMT + '/tag', data="second", verify=False)
        assert 204 == resp.status_code

        for _ in range(4):
            resp = httpx.post(MGMT + '/async/producers/dataset', verify=False)
            assert 202 == resp.status_code

        self.assert_async_consume(self.assert_post_async_dataset_part3)

    def assert_post_async_dataset_fromfile(self):
        resp = httpx.get(MGMT + '/async/consumers/consumer-for-dataset-fromfile', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        for key, value, headers in [
            ('key15', 'dset: val1', {'hdr15': 'val15'}),
            ('key15', 'dset: val2', {'hdr15': 'val15'}),
            ('key15', 'dset: val3', {'hdr15': 'val15'}),
        ]:
            self.assert_consumer_log(data, key, value, headers)

        assert len(data['log']['entries']) == 3

    def test_post_async_dataset_fromfile(self):
        for _ in range(3):
            resp = httpx.post(MGMT + '/async/producers/dataset-fromfile', verify=False)
            assert 202 == resp.status_code

        self.assert_async_consume(self.assert_post_async_dataset_fromfile)

    def assert_post_async_dataset_no_matching_tags(self):
        resp = httpx.get(MGMT + '/async/consumers/consumer-for-dataset-no-matching-tags', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        for key, value, headers in [
            ('key14', 'dset: {{var}}', {'hdr14': 'val14'}),
        ]:
            self.assert_consumer_log(data, key, value, headers)

    def test_post_async_dataset_no_matching_tags(self):
        resp = httpx.post(MGMT + '/tag', data="", verify=False)
        assert 204 == resp.status_code

        resp = httpx.post(MGMT + '/async/producers/dataset-no-matching-tags', verify=False)
        assert 202 == resp.status_code

        self.assert_async_consume(self.assert_post_async_dataset_no_matching_tags)

    def test_post_async_dataset_nonlooped(self):
        for _ in range(2):
            resp = httpx.post(MGMT + '/async/producers/dataset-nonlooped', verify=False)
            assert 202 == resp.status_code

        resp = httpx.post(MGMT + '/async/producers/dataset-nonlooped', verify=False)
        assert 410 == resp.status_code

    def test_delete_async_consumer_bad_requests(self):
        resp = httpx.delete(MGMT + '/async/consumers/99', verify=False)
        assert 400 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'Invalid consumer index!'

        actor_name = 'not-existing-actor'
        resp = httpx.delete(MGMT + '/async/consumers/%s' % actor_name, verify=False)
        assert 400 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'No consumer actor is found for: %r' % actor_name

    def test_traffic_log_async(self):
        global async_service_type

        resp = httpx.get(MGMT + '/traffic-log', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        jsonschema_validate(data, HAR_JSON_SCHEMA)

        entries = data['log']['entries']

        assert any(
            entry['request']['method'] == 'PUT'
            and  # noqa: W504, W503
            entry['request']['url'] == '%s://localhost:%s/topic1%s' % (async_service_type, ASYNC_ADDR[async_service_type].split(':')[1], '?key=key1' if async_service_type != 'redis' else '')
            and  # noqa: W504, W503
            entry['response']['status'] == 202
            for entry in entries
        )

        if async_service_type == 'redis':
            assert any(
                entry['request']['method'] == 'GET'
                and  # noqa: W504, W503
                entry['request']['url'] == '%s://localhost:%s/topic2' % (async_service_type, ASYNC_ADDR[async_service_type].split(':')[1])
                and  # noqa: W504, W503
                entry['response']['status'] == 200
                for entry in entries
            )
        else:
            assert any(
                entry['request']['method'] == 'GET'
                and  # noqa: W504, W503
                entry['request']['url'] == '%s://localhost:%s/topic2?key=key2' % (async_service_type, ASYNC_ADDR[async_service_type].split(':')[1])
                and  # noqa: W504, W503
                entry['response']['status'] == 200
                and  # noqa: W504, W503
                entry['response']['headers'][-1]['name'] == 'X-%s-Message-Key' % PROGRAM.capitalize()
                and  # noqa: W504, W503
                entry['response']['headers'][-1]['value'] == 'key2'
                for entry in entries
            )

        if async_service_type == 'redis':
            assert any(
                entry['request']['method'] == 'GET'
                and  # noqa: W504, W503
                entry['request']['url'] == '%s://localhost:%s/topic3' % (async_service_type, ASYNC_ADDR[async_service_type].split(':')[1])
                and  # noqa: W504, W503
                entry['response']['status'] == 200
                for entry in entries
            )
        else:
            assert any(
                entry['request']['method'] == 'GET'
                and  # noqa: W504, W503
                entry['request']['url'] == '%s://localhost:%s/topic3?key=key3' % (async_service_type, ASYNC_ADDR[async_service_type].split(':')[1])
                and  # noqa: W504, W503
                entry['response']['status'] == 200
                and  # noqa: W504, W503
                entry['response']['headers'][-1]['name'] == 'X-%s-Message-Key' % PROGRAM.capitalize()
                and  # noqa: W504, W503
                entry['response']['headers'][-1]['value'] == 'key3'
                for entry in entries
            )

        assert any(
            entry['request']['method'] == 'PUT'
            and  # noqa: W504, W503
            entry['request']['url'] == '%s://localhost:%s/topic3%s' % (async_service_type, ASYNC_ADDR[async_service_type].split(':')[1], '?key=key3' if async_service_type != 'redis' else '')
            and  # noqa: W504, W503
            entry['response']['status'] == 202
            for entry in entries
        )

        assert any(
            entry['request']['method'] == 'PUT'
            and  # noqa: W504, W503
            entry['request']['url'] == '%s://localhost:%s/topic6' % (async_service_type, ASYNC_ADDR[async_service_type].split(':')[1])
            and  # noqa: W504, W503
            entry['response']['status'] == 202
            for entry in entries
        )

        assert any(
            entry['request']['method'] == 'PUT'
            and  # noqa: W504, W503
            entry['request']['url'] == '%s://localhost:%s/topic7%s' % (async_service_type, ASYNC_ADDR[async_service_type].split(':')[1], '?key=key7' if async_service_type != 'redis' else '')
            and  # noqa: W504, W503
            entry['response']['status'] == 202
            for entry in entries
        )

        assert any(
            entry['request']['method'] == 'PUT'
            and  # noqa: W504, W503
            entry['request']['url'] == '%s://localhost:%s/topic8%s' % (async_service_type, ASYNC_ADDR[async_service_type].split(':')[1], '?key=key8' if async_service_type != 'redis' else '')
            and  # noqa: W504, W503
            entry['response']['status'] == 202
            for entry in entries
        )

        if async_service_type == 'redis':
            assert any(
                entry['request']['method'] == 'PUT'
                and  # noqa: W504, W503
                entry['request']['url'].startswith('%s://localhost:%s/templated-producer' % (async_service_type, ASYNC_ADDR[async_service_type].split(':')[1]))
                and  # noqa: W504, W503
                entry['response']['status'] == 202
                for entry in entries
            )
        else:
            assert any(
                entry['request']['method'] == 'PUT'
                and  # noqa: W504, W503
                entry['request']['url'].startswith('%s://localhost:%s/templated-producer?key=prefix-' % (async_service_type, ASYNC_ADDR[async_service_type].split(':')[1]))
                and  # noqa: W504, W503
                entry['request']['headers'][-2]['value'].isnumeric()
                and  # noqa: W504, W503
                entry['request']['headers'][-1]['value'].startswith('Some text')
                and  # noqa: W504, W503
                entry['response']['status'] == 202
                for entry in entries
            )

    def test_stats(self):
        global async_service_type

        resp = httpx.get(MGMT + '/stats', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

        data = resp.json()
        assert data['global']['request_counter'] > 20
        assert data['global']['avg_resp_time'] == 0
        assert data['global']['status_code_distribution']['200'] > 8
        assert data['global']['status_code_distribution']['202'] > 8

        assert data['services'][0]['hint'] == 'Asynchronous Mocks'
        assert data['services'][0]['request_counter'] > 20
        assert data['services'][0]['avg_resp_time'] == 0
        assert data['services'][0]['status_code_distribution']['200'] > 8
        assert data['services'][0]['status_code_distribution']['202'] > 8
        assert len(data['services'][0]['endpoints']) == 37

        assert data['services'][0]['endpoints'][0]['hint'] == 'PUT topic1 - 0'
        assert data['services'][0]['endpoints'][0]['request_counter'] == 1
        assert data['services'][0]['endpoints'][0]['avg_resp_time'] == 0
        assert data['services'][0]['endpoints'][0]['status_code_distribution'] == {'202': 1}

        assert data['services'][0]['endpoints'][1]['hint'] == 'GET topic2 - 1'
        assert data['services'][0]['endpoints'][1]['request_counter'] == 6 if async_service_type == 'redis' else 2
        assert data['services'][0]['endpoints'][1]['avg_resp_time'] == 0
        assert data['services'][0]['endpoints'][1]['status_code_distribution'] == {'200': 6} if async_service_type == 'redis' else {'200': 2}

        assert data['services'][0]['endpoints'][2]['hint'] == 'PUT topic3 - 2'
        assert data['services'][0]['endpoints'][2]['request_counter'] > 1
        assert data['services'][0]['endpoints'][2]['avg_resp_time'] == 0
        assert data['services'][0]['endpoints'][2]['status_code_distribution']['202'] > 1
        assert data['services'][0]['endpoints'][2]['status_code_distribution']['202'] == data['services'][0]['endpoints'][2]['request_counter']

        assert data['services'][0]['endpoints'][3]['hint'] == 'GET topic3 - 3'
        assert data['services'][0]['endpoints'][3]['request_counter'] > 0
        assert data['services'][0]['endpoints'][3]['avg_resp_time'] == 0
        assert data['services'][0]['endpoints'][3]['status_code_distribution']['200'] > 0
        assert data['services'][0]['endpoints'][3]['status_code_distribution']['200'] == data['services'][0]['endpoints'][3]['request_counter']

        assert data['services'][0]['endpoints'][4]['hint'] == 'GET topic4 - 4'
        assert data['services'][0]['endpoints'][4]['request_counter'] == 1
        assert data['services'][0]['endpoints'][4]['avg_resp_time'] == 0
        assert data['services'][0]['endpoints'][4]['status_code_distribution'] == {'200': 1}

        assert data['services'][0]['endpoints'][5]['hint'] == 'PUT topic5 - 4'
        assert data['services'][0]['endpoints'][5]['request_counter'] == 1
        assert data['services'][0]['endpoints'][5]['avg_resp_time'] == 0
        assert data['services'][0]['endpoints'][5]['status_code_distribution'] == {'202': 1}

        assert data['services'][0]['endpoints'][6]['hint'] == 'PUT topic6 - 5 (actor: actor6)'
        assert data['services'][0]['endpoints'][6]['request_counter'] == 1
        assert data['services'][0]['endpoints'][6]['avg_resp_time'] == 0
        assert data['services'][0]['endpoints'][6]['status_code_distribution'] == {'202': 1}

        assert data['services'][0]['endpoints'][7]['hint'] == 'PUT topic7 - 6 (actor: limitless)'
        assert data['services'][0]['endpoints'][7]['request_counter'] > 0
        assert data['services'][0]['endpoints'][7]['avg_resp_time'] == 0
        assert data['services'][0]['endpoints'][7]['status_code_distribution']['202'] > 0
        assert data['services'][0]['endpoints'][7]['status_code_distribution']['202'] == data['services'][0]['endpoints'][7]['request_counter']

        assert data['services'][0]['endpoints'][8]['hint'] == 'PUT topic8 - 7 (actor: short-loop)'
        assert data['services'][0]['endpoints'][8]['request_counter'] > 5
        assert data['services'][0]['endpoints'][8]['avg_resp_time'] == 0
        assert data['services'][0]['endpoints'][8]['status_code_distribution']['202'] > 5

        assert data['services'][0]['endpoints'][9]['hint'] == 'GET topic9 - 8 (actor: actor9)'
        assert data['services'][0]['endpoints'][9]['request_counter'] == 0
        assert data['services'][0]['endpoints'][9]['avg_resp_time'] == 0
        assert data['services'][0]['endpoints'][9]['status_code_distribution'] == {}

        assert data['services'][0]['endpoints'][10]['hint'] == 'PUT templated-producer - 9 (actor: templated-producer)'
        assert data['services'][0]['endpoints'][10]['request_counter'] == 2
        assert data['services'][0]['endpoints'][10]['avg_resp_time'] == 0
        assert data['services'][0]['endpoints'][10]['status_code_distribution'] == {'202': 2}

        assert data['services'][0]['endpoints'][11]['hint'] == 'GET topic10 - 10'
        assert data['services'][0]['endpoints'][11]['request_counter'] == 3
        assert data['services'][0]['endpoints'][11]['avg_resp_time'] == 0
        assert data['services'][0]['endpoints'][11]['status_code_distribution'] == {'200': 3}

        assert data['services'][1]['hint'] == 'http://service1.example.com:8001 - Mock for Service1'
        assert data['services'][1]['request_counter'] == 0
        assert data['services'][1]['avg_resp_time'] == 0
        assert data['services'][1]['status_code_distribution'] == {}
        assert len(data['services'][1]['endpoints']) == 0

        assert data['services'][2]['hint'] == '%s://localhost:%s' % (async_service_type, str(int(ASYNC_ADDR[async_service_type].split(':')[1]) + 1))
        assert data['services'][2]['request_counter'] == 0
        assert data['services'][2]['avg_resp_time'] == 0
        assert data['services'][2]['status_code_distribution'] == {}
        assert len(data['services'][2]['endpoints']) == 2

    def assert_management_post_config(self, async_consumer):
        global async_service_type

        key = 'key1'
        value = 'value101'
        headers = {
            'hdr1': 'val1',
            'global-hdrX': 'globalvalY',
            'global-hdr2': 'globalval2'
        }

        if async_service_type == 'redis':
            assert any(row[1] == value for row in async_consumer.log)
        else:
            assert any(row[0] == key and row[1] == value and row[2] == headers for row in async_consumer.log)

        key = 'key301'
        value = 'value3'
        headers = {
            'hdr3': 'val301',
            'global-hdrX': 'globalvalY',
            'global-hdr2': 'globalval2'
        }

        resp = httpx.get(MGMT + '/async/consumers/1', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        self.assert_consumer_log(data, key, value, headers)

    def test_management_post_config(self):
        global async_service_type

        resp = httpx.get(MGMT + '/config', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        if async_service_type != 'redis':
            del data['globals']['headers']['global-hdr1']
            data['globals']['headers']['global-hdrX'] = 'globalvalY'
            data['services'][0]['actors'][2]['produce']['key'] = 'key301'
            data['services'][0]['actors'][2]['produce']['headers']['hdr3'] = 'val301'

        data['services'][0]['actors'][0]['produce']['value'] = 'value101'
        data['services'][0]['actors'][2]['delay'] = 2

        resp = httpx.post(MGMT + '/config', data=json.dumps(data), verify=False)
        assert 204 == resp.status_code

        time.sleep(ASYNC_CONSUME_WAIT / 10)

        queue, job = start_render_queue()
        async_service = getattr(sys.modules[__name__], '%sService' % async_service_type.capitalize())(
            ASYNC_ADDR[async_service_type],
            definition=DefinitionMockForAsync(None, PYBARS, queue)
        )
        async_actor = getattr(sys.modules[__name__], '%sActor' % async_service_type.capitalize())(0)
        async_service.add_actor(async_actor)
        async_consumer = getattr(sys.modules[__name__], '%sConsumer' % async_service_type.capitalize())('topic1', enable_topic_creation=True)
        async_actor.set_consumer(async_consumer)
        async_consumer_group = getattr(sys.modules[__name__], '%sConsumerGroup' % async_service_type.capitalize())()
        async_consumer_group.add_consumer(async_consumer)
        t = threading.Thread(target=async_consumer_group.consume, args=(), kwargs={})
        t.daemon = True
        t.start()

        resp = httpx.post(MGMT + '/async/producers/0', verify=False)
        assert 202 == resp.status_code

        self.assert_async_consume(
            self.assert_management_post_config,
            async_consumer
        )

        async_consumer_group._stop()
        t.join()
        job.kill()

    def test_management_get_resources(self):
        global async_service_type

        resp = httpx.get(MGMT + '/resources', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        if async_service_type == 'redis':
            assert data == {'files': ['dataset.json', 'image.png', 'value_schema.json', 'value_schema_error.json']}
        else:
            assert data == {'files': ['dataset.json', 'image.png', 'templates/example.txt', 'value_schema.json', 'value_schema_error.json']}


class TestAsyncKafka(AsyncBase):

    @classmethod
    def setup_class(cls):
        global async_service_type

        async_service_type = 'kafka'
        super().setup_class()


class TestAsyncAMQP(AsyncBase):

    @classmethod
    def setup_class(cls):
        global async_service_type

        async_service_type = 'amqp'
        super().setup_class()


class TestAsyncRedis(AsyncBase):

    @classmethod
    def setup_class(cls):
        global async_service_type

        async_service_type = 'redis'
        super().setup_class()
