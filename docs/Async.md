# Asynchronous Actors for Message Bus

Mockintosh offers "Mock Actor" approach for using with asynchronous message bus technologies, such as Kafka, RabbitMQ
and Redis. "Mock Actor" approach requires you to provide deployed message bus instance, and configure valid address for
it inside configuration file.

Each Mock Actor is an entity that can be configured for producing or consuming messages, or both. Management API
provides important synergies to work with Mock Actors.

To start creating Mock Actors in Mockintosh config, you need to configure a service, with `type` option set
into `kafka`:

```yaml
services:
  - name: Kafka Mock Actors
    type: kafka
    address: localhost:9092  # broker string of pre-existing Kafka instance
    actors: [ ]  # here we will configure the actors, see below
```

Below are the configuration patterns for Mock Actors:

## Scheduled Producer

Below is the configuration snippet for Mock Actor that will produce configured message each `delay` seconds, up
to `limit` times. The `delay` option is key for this case, it distinguishes scheduled producer from "on-demand producer"
.

```yaml
services:
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
        limit: 100  # limit of how many messages to produce, optional 
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
          queue: on-demand1
          key: somekey or null
          value: "@value/from/file.json"  # it's possible to reference file
```

Now, to trigger producing the message on-demand, you need to issue an API call using actor's `name`, like this:

```shell
curl -X POST http://localhost:8000/async/on-demand-1 
```

_Note: The `limit` option actually works for any kind of producer._

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
curl http://localhost:8000/async/validate-consume-1 
```

That would respond with JSON containing the list of captured messages, for example:

```json5
TODO
```

To clear the captured message list, issue a `DELETE` call on the same URL:

```shell
curl -X DELETE http://localhost:8000/async/validate-consume-1
```

To narrow down the expected message, you can use regular [matching](Management.md) equations in `key`, `value`
or `headers` values:

```yaml
management:
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
            hdr-name: "{{regEx 'prefix-(.+)-suffix' 'myCapturedVar'}}" # see also "reactive producer" section
```

## "Reactive" Producer

By mixing together actors of "validating consumer" and "on-demand producer" types, we can get the behavior when message
is produced in "reaction" to another message consumed from the bus. You can also specify a `delay` between consumption
and producing, to simulate some "processing time".