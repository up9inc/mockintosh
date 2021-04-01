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
automatically, this kind of actor waits for Management API call to trigger the message push.

## "Reactive" Producer

## Validating Consumer

