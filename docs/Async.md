# Asynchronous Actors for Message Bus

Mockintosh offers "Mock Actor" approach for using with asynchronous message bus technologies, such as
[Apache Kafka](https://kafka.apache.org/), [RabbitMQ](https://www.rabbitmq.com/),
[Apache ActiveMQ](https://activemq.apache.org/), [Redis](https://redis.io/) etc.
or cloud services such as [Google Cloud Pub/Sub](https://cloud.google.com/pubsub),
[Amazon SQS](https://aws.amazon.com/sqs/) etc.
See [supported backends](#supported-backends).
"Mock Actor" approach requires you to provide deployed message bus instance, and configure valid address for it inside
configuration file.

Each Mock Actor is an entity that can be configured for producing or consuming messages or
both. [Management API/UI](Management.md)
provides important synergies to work with Mock Actors.

To start creating Mock Actors in Mockintosh config, you need to configure a service, with `type` option set
into `kafka`:

```yaml
services:
  - name: Kafka Mock Actors
    type: kafka
    address: localhost:9092  # broker string of pre-existing Kafka instance
    ssl: true
    actors: [ ]  # here we will configure the actors, see below
```

If you're connecting to a Kafka cluster through SSL you need to set `ssl` field to `true`. By default SSL is disabled.

> Note: The `address` field of asynchronous services supports templating. Such that the address can be fetched
> from an environment variable like: `address: "{% raw %}{{env 'KAFKA' 'localhost:9092'}}{% endraw %}"`

Below are the configuration patterns for Mock Actors:

## Scheduled Producer

Below is the configuration snippet for Mock Actor that will produce configured message each `delay` seconds, up
to `limit` times. The `delay` option is key for this case, it distinguishes scheduled producer
from ["on-demand producer"](#on-demand-producer).

```yaml
{% raw %}services:
  - name: Kafka Mock Actors
    type: kafka
    address: localhost:9092
    actors:
      - name: scheduled-producer-1  # just the name
        produce:
          queue: scheduled-queue1  # topic/queue name
          key: "message key, can be null"
          value: "message value"
          headers:
            constant: justvalue
            timestamp: '{{date.timestamp}}'  # regular Mockintosh templating can be used

        delay: 5  # seconds between producing
        limit: 100  # limit of how many messages to produce, optional{% endraw %}
```

You can use most of Mockintosh [templating](Templating.md) equations, with exception of those dependant on `request`.
Queue name and header names cannot be templated.

_Note: Be careful with setting `delay` to low value with no `limit` option, this may run your message bus out of
memory/disk space._

## On-Demand Producer

On-demand producer is basically a scheduled producer with no `delay` option. Instead of producing messages
automatically, this kind of actor waits for [Management API](Management.md) call to trigger the message push.

```yaml
management:
  port: 8000
services:
  - name: Kafka Mock Actors
    type: kafka
    address: localhost:9092
    actors:
      - name: on-demand-1
        produce:
          create: true
          queue: on-demand1
          key: somekey or null
          value: "@value/from/file.json"  # it's possible to reference file
```

Now, to trigger producing the message on-demand, you need to issue an API call using actor's `name`, like this:

```shell
curl -X POST http://localhost:8000/async/producers/on-demand-1
```

and the response of this request would be;

```json
{
  "type": "kafka",
  "name": "on-demand-1",
  "index": 0,
  "queue": "on-demand1",
  "lastProduced": 1618695168.6416173
}
```

> Note: `create: true` flag enables the topic creation if the given topic is not created yet.

It's also possible to select the producer using its [`index`](#asynchronous-index) number as an alternative to the
actor's `name` like:

```shell
curl -X POST http://localhost:8000/async/producers/0
```

_Note: The `limit` option actually works for any kind of producer._

### Triggering a Producer From an HTTP Endpoint

It's possible trigger an asynchronous producer from an HTTP endpoint using the `triggerAsyncProducer` field.
The value of this field can be either a possitive integer that indicates the global index of a producer or
a string that selects the producer based on its name:

```yaml
management:
  port: 8000
services:
  - name: Mock for Service1
    port: 8001
    endpoints:
    - path: "/endp1"
      response:
        body: "endp1"
        triggerAsyncProducer: 0
    - path: "/endp2"
      response:
        body: "endp2"
        triggerAsyncProducer: on-demand-1
  - name: Kafka Mock Actors
    type: kafka
    address: localhost:9092
    actors:
      - name: on-demand-1
        produce:
          create: true
          queue: on-demand1
          key: somekey or null
          value: "@value/from/file.json"  # it's possible to reference file
```

The producer `on-demand-1` that's linked to the HTTP endpoints via the `triggerAsyncProducer` field is triggered
whenever the an HTTP request is matched into the subject endpoint and the related response is returned.

## Validating Consumer

The "validating consumer" actor is used when you need to check the fact of service publishing the message on the bus.
For example, if your service accepts REST call and puts message on the bus, and you validating this behavior in an
automated test. Again, for this validating you would need to have [Management API](Management.md) enabled. Let's see a
snippet:

```yaml
management:
  port: 8000
services:
  - name: Kafka Mock Actors
    type: kafka
    address: localhost:9092
    actors:
      - name: validate-consume-1
        consume:
          queue: another-queue-name # topic/queue name to subscribe to, required
          group: "consumer-group" # optional consumer group
          key: matching keys  # expected key, optional
          value: "expected value"  # optional
          capture: 10  # limit len of messages to store for validation, optional, default: 1
```

To validate that message has appeared on the bus, you have to query Management API endpoint, like this:

```shell
curl http://localhost:8000/async/consumers/validate-consume-1
```

That would respond with a JSON containing the list of captured messages in
the [HAR](http://www.softwareishard.com/blog/har-12-spec/) format, that's quite similar to the responses you can see
in [Traffic Logs](Management.md#traffic-logs). The traffic logging is specific to the selected consumer. The consumer
will store last N messages, according to its `capture` setting.

To clear the captured message list, issue a `DELETE` call on the same URL:

```shell
curl -X DELETE http://localhost:8000/async/consumers/validate-consume-1
```

To narrow down the expected message, you can use regular [matching](Management.md) equations in `key`, `value`
or `headers` values:

```yaml
{% raw %}management:
  port: 8000
services:
  - name: Kafka Mock Actors
    type: kafka
    address: localhost:9092
    actors:
      - name: validate-consume-2
        consume:
          queue: another-queue-name
          key: "{{regEx 'prefix-(.*)'}}"
          value: "expected prefix-{{justName}}"  # see also "reactive producer" section
          headers:
            hdr-name: "{{regEx 'prefix-(.+)-suffix' 'myCapturedVar'}}" # see also "reactive producer" section{% endraw %}
```

### JSONSchema

The `value` field supports [JSON Schema](https://json-schema.org/) matching much like how
[it's in HTTP](Matching.md#jsonschema). Except it's the `schema` field used instead of or with the `value` field:

```yaml
{% raw %}- consume:
    queue: validate-consume-3
    key: "{{regEx 'prefix-(.*)'}}"
    schema:
      type: object
      properties:
        somekey: { }
      required:
        - somekey
    headers:
      hdr-name: "{{regEx 'prefix-(.+)-suffix' 'myCapturedVar'}}"{% endraw %}
```

If the `schema` field used together with the `value` then both are taken into account as the criteria for matching.

Referencing JSONSchema from an external file is also supported:

```yaml
{% raw %}- consume:
    queue: validate-consume-3
    key: "{{regEx 'prefix-(.*)'}}"
    schema: "@path/to/schema.json"
    headers:
      hdr-name: "{{regEx 'prefix-(.+)-suffix' 'myCapturedVar'}}"{% endraw %}
```

## "Reactive" Producer

By mixing together actors of "validating consumer" and "on-demand producer" types, we can get the behavior when message
is produced in "reaction" to another message consumed from the bus. You can also specify a `delay` between consumption
and producing, to simulate some "processing time".

```yaml
{% raw %}services:
  - name: Kafka Mock Actors
    type: kafka
    address: localhost:9092
    actors:
      - name: reactive-producer-1
        consume:
          queue: consume-from-topic-1
          key: "{{regEx 'prefix-(.*)'}}"
          value: "expected prefix-{{justName}}"  # see also "reactive producer" section
          headers:
            hdr-name: "{{regEx 'prefix-(.+)-suffix' 'myCapturedVar'}}" # see also "reactive producer" section
        delay: 5  # optional delay before producing
        produce:
          queue: produce-into-topic-2
          key: "can reference as {{consumed.key}} and {{consumed.value}}"
          value: "reference from consumed: {{justName}} {{myCapturedVar}}"
          headers:
            propagated-hdr: '{{consumed.headers.hdr-name}}'{% endraw %}
```

_Note: Validating the consumer and triggering the producing would work for "reactive producer", too._

## Extended Features

### Asynchronous Index

For a configuration file like:

```yaml
management:
  port: 8000
services:
  - name: Kafka Mock Actors
    type: kafka
    address: localhost:9092
    actors:
      - name: on-demand-1
        produce:
          queue: on-demand1
          key: somekey or null
          value: "@value/from/file.json"
      - name: validate-consume-1
        consume:
          queue: another-queue-name
          group: "consumer-group"
          key: matching keys
          value: "expected value"
          capture: 10
```

the `/async` management endpoint, returns an index that contains `producers` and `consumers` lists:

```bash
$ curl http://localhost:8000/async
{
  "producers": [
    {
      "type": "kafka",
      "name": "on-demand-1",
      "index": 0,
      "queue": "on-demand1",
      "producedMessages": 0,
      "lastProduced": null
    }
  ],
  "consumers": [
    {
      "type": "kafka",
      "name": "validate-consume-1",
      "index": 0,
      "queue": "another-queue-name",
      "captured": 0,
      "consumedMessages": 0,
      "lastConsumed": null
    }
  ]
}
```

`captured` field resembles the number of consumed messages that stored in the buffer while `consumedMessages` field
resembles the number of all consumed messages throught the message stream.

### Multiple Payloads

Similar to the [multiple responses](Configuring.md#multiple-responses) in HTTP, asynchronous producers support tagged
payloads. Which means they can be a list of `queue`, `key`, `value`, `headers` combinations (JSON array)
instead of being a single combination (JSON object):

```yaml
produce:
  - queue: topicA
    key: keyA-1
    value: valueA-1
    headers:
      hdrA-1: valA-1
  - queue: topicA
    key: keyA-2
    value: valueA-2
    headers:
      hdrA-2: valA-2
```

1. trigger: `valueA-1` is produced as `value`.
2. trigger: `valueA-2` is produced as `value`.
3. trigger: `valueA-1` is produced as `value`.

By default a producer loops through its payloads indefinitely for each trigger. To disable this behavior, set
`multiPayloadsLooped` to `false` similar to `multiResponsesLooped` in HTTP.

_Note: Supplying different topics for multiple payloads throws a compile-time error._

### Tagged Payloads

Similar to the [tagged responses](Configuring.md#tagged-responses) in HTTP, it's possible to select certain payload or
payloads using the `tag` field:

```yaml
produce:
  - queue: topicA
    key: keyA-1
    value: valueA-1
    headers:
      hdrA-1: valA-1
  - queue: topicA
    tag: async-tagA-3
    key: keyA-3
    value: valueA-3
    headers:
      hdrA-3: valA-3
  - queue: topicA
    key: keyA-2
    value: valueA-2
    headers:
      hdrA-2: valA-2
```

"**Tags**" is a generic feature so [Setting Current Tag](Management.md#setting-current-tag)
and [Resetting Iterators](Management.md#resetting-iterators) are valid for asynchronous tags too.

### Datasets

Similar to the [datasets](Configuring.md#datasets) in HTTP, one can put a `dataset` field under `actor`
to specify a list of key-value combinations to inject into response templating.

This field can be a string that starts with `@` to indicate a path to an external JSON file like `@subdir/dataset.json`
or an array:

```yaml
{% raw %}dataset:
  - var1: val1
  - var1: val2
produce:
  - queue: topic1
    key: key1
    value: "dset: {{var1}}"{% endraw %}
```

1. trigger: `dset: val1` is produced as `value`.
2. trigger: `dset: val2` is produced as `value`.
3. trigger: `dset: val1` is produced as `value`.

By default a producer loops through the given dataset indefinitely for each trigger. To disable this behavior, set
`datasetLooped` to `false` similar to `datasetLooped` in HTTP.

## Supported Backends

Mockintosh supports three different asynchronous backends;
[Apache Kafka](https://kafka.apache.org/), [AMQP](https://www.amqp.org/) and [Redis](https://redis.io/).

### Apache Kafka

To be able to work with Apache Kafka, these two fields should be specified in a service:

```yaml
type: kafka
address: localhost:9092
```

The `kafka` value for the `type` field is a keyword and `<HOST>:<PORT>` configuration in the `address` field should match
to the Apache Kafka instance's hostname/IP and port.

### Advanced Message Queuing Protocol (AMQP)

AMQP as an [OASIS](https://en.wikipedia.org/wiki/OASIS_(organization)) standard is a widely accepted protocol
accross the asynchronous message queue software such as;

-   [RabbitMQ](https://www.rabbitmq.com/)
-   [Apache ActiveMQ](https://activemq.apache.org/)
-   [Apache Qpid](https://qpid.apache.org/)
-   [JORAM](https://joram.ow2.io/)

and cloud services such as;

-   [Amazon MQ](https://aws.amazon.com/amazon-mq/?amazon-mq.sort-by=item.additionalFields.postDateTime&amazon-mq.sort-order=desc)
-   [Azure Event Hubs](https://docs.microsoft.com/en-us/azure/event-hubs/event-hubs-about)
-   [Azure Service Bus](https://docs.microsoft.com/en-us/azure/service-bus-messaging/service-bus-messaging-overview)
-   [Solace](https://solace.com/)

To be able to work with AMQP, these two fields should be specified in a service:

```yaml
type: amqp
address: localhost:5672
```

The `amqp` value for the `type` field is a keyword and `<HOST>:<PORT>` configuration in the `address` field should match
to the AMQP target hostname/IP and port.

*Note: `rabbitmq` and `activemq` as a value for the `type` field instead of `amqp` is also accepted.*

#### Properties Object

It's possible to supply an additional `amqpProperties` field to fill the keyword arguments
in [`pika.spec.BasicProperties`](https://pika.readthedocs.io/en/stable/modules/spec.html?highlight=BasicProperties#pika.spec.BasicProperties)
except the `headers` argument. `headers` argument is set by just the common `headers` field.

So for example, to mock the [`convertAndSend`](https://docs.spring.io/spring-amqp/docs/latest_ga/api/org/springframework/amqp/rabbit/core/RabbitTemplate.html#convertAndSend-java.lang.String-java.lang.Object-) function of [`org.springframework.amqp.rabbit.core.RabbitTemplate`](https://docs.spring.io/spring-amqp/docs/latest_ga/api/org/springframework/amqp/rabbit/core/RabbitTemplate.html) class you would simply use these
`amqpProperties`:

```yaml
queue: queue1
value: '{"message":"OK"}'
amqpProperties:
  priority: 0
  delivery_mode: 2
  content_encoding: "UTF-8"
  content_type: "application/json"
headers:
  __TypeId__: "com.example.ClassName"
```

### Redis

[Redis](https://redis.io/) as an in-memory database, can also be used as a message queue. But note that;
`key` and `headers` fields are ignored for Redis type asynchronous services since Redis does not have
such concepts. Message queue functionality through Redis
is achived by [PyRSMQ](https://mlasevich.github.io/PyRSMQ/) package.

To be able to work with Redis, these two fields should be specified in a service:

```yaml
type: redis
address: localhost:6379
```

The `redis` value for the `type` field is a keyword and `<HOST>:<PORT>` configuration in the `address` field should match
to the Redis instance's hostname/IP and port.

### Google Cloud Pub/Sub

[Google Cloud Pub/Sub](https://cloud.google.com/pubsub) is a message queue cloud service of Google. There are several
ways to work with Pub/Sub;

#### Testing against Google Cloud Platform

One is specifying the project ID and the path to the service account JSON file in your Mockintosh config:

```yaml
type: gpubsub
address: project-id-111111@/path/to/project-id-111111.json
```

The other way is setting the environment variables `GOOGLE_APPLICATION_CREDENTIALS` and `GOOGLE_CLOUD_PROJECT`
while setting service type to `gpubsub`:

```bash
$ GOOGLE_APPLICATION_CREDENTIALS="/path/to/project-id-111111.json" \
    GOOGLE_CLOUD_PROJECT="project-id-111111" \
    mockintosh config.yaml
```

#### Testing against Pub/Sub emulator

Google provides an emulator for Pub/Sub and can be installed
by following [this official tutorial](https://cloud.google.com/pubsub/docs/emulator).
Alternatively, there are community Docker images
like [messagebird/gcloud-pubsub-emulator](https://hub.docker.com/r/messagebird/gcloud-pubsub-emulator) which
can be used instead of installing the emulator locally.

Once the Pub/Sub emulator is up and running, you can start Mockintosh
by setting `PUBSUB_EMULATOR_HOST` and `PUBSUB_PROJECT_ID` environment variables while setting service type to `gpubsub`:

```bash
$ PUBSUB_EMULATOR_HOST="localhost:8681" \
    PUBSUB_PROJECT_ID="project-id" \
    mockintosh config.yaml
```

### Amazon Simple Queue Service

#### Testing against AWS

[Amazon Simple Queue Service](https://aws.amazon.com/sqs/) is a message queue cloud service of Amazon. There are several
ways to work with Amazon SQS;

One is specifying the AWS credentials,
a [legacy endpoint](https://docs.aws.amazon.com/general/latest/gr/sqs-service.html)
and the region as a URI format `<SCHEME>://<AWS_ACCESS_KEY_ID>:<AWS_SECRET_ACCESS_KEY>@<ENDPOINT>:<PORT>#<REGION>` in the `address` field:

The `<SCHEME>`/`<PORT>` combination can be one of these:

| `<SCHEME>`  | `<PORT>`    | Description          |
| ----------- | ----------- | -------------------- |
| `http`      | `80`        | `use_ssl` is `false` |
| `https`     | `443`       | `use_ssl` is `true`  |

```yaml
type: amazonsqs
address: https://<AWS_ACCESS_KEY_ID>:<AWS_SECRET_ACCESS_KEY>@us-east-2.queue.amazonaws.com:443#us-east-2
```

The `<AWS_ACCESS_KEY_ID>` and `<AWS_SECRET_ACCESS_KEY>` parts of the address are omitted if the
`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` environment variables are set.

```bash
$ AWS_ACCESS_KEY_ID="<AWS_ACCESS_KEY_ID>" \
    AWS_SECRET_ACCESS_KEY="<AWS_SECRET_ACCESS_KEY>" \
    mockintosh config.yaml
```

#### Testing against ElasticMQ

[ElasticMQ](https://github.com/softwaremill/elasticmq) is an in-memory message queue with an Amazon SQS-compatible
interface. Such that it provides a way to test Amazon SQS integration behavior locally.

You can directly run ElasticMQ using Java `java -jar elasticmq-server-X.Y.Z.jar` or you can use
the [softwaremill/elasticmq](https://hub.docker.com/r/softwaremill/elasticmq) Docker image.

Use the `address` below to establish a connection to local ElasticMQ instance:

```yaml
type: amazonsqs
address: http://localhost:9324#elasticmq
```
