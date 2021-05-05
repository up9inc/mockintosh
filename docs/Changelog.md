# Changelog

## v0.9 - 2021-05-04

1. Mock Actors implementation for Kafka
    - on schedule producer
    - on demand producer
    - reactive consumer+producer
    - consumer fact validation
2. Display timestamps in traffic log, instead of offset
3. Introduce `env` function for templating
4. Do not respond with Content-Type=text/html if no content-type header is configured
5. Make `MOCKINTOSH_FORCE_PORT` to work always
6. CLI argument to set the tag enabled, forbid comma in tag name
7. Alternative base directory for resource files via `MOCKINTOSH_DATA_DIR`
8. Fix missing `request.path.<n>` support in templating

## v0.8.2 - 2021-04-07

1. Cleaner config templates from "unhandled" in mgmt API
2. Fix traffic not logged inside docker-compose setup
3. Less logging around fallback

## v0.8.1 - 2021-03-21

1. Fix bug in management UI resource editor
2. Proper support for query string written in `path` option

## v0.8 - 2021-03-20

1. [Management API/UI](Management.md) Improvements:
    1. Overall visual look tuning
    1. change config editor component in management UI
    1. YAML format for unhandled requests
    1. allow editing resource files via mgmt API/UI
    1. traffic log API & viewer
    1. mgmt UI change config global section didn't work
    1. report error in case config apply fails
    1. add UI for /tag management API
    1. Improve stats display

1. `fallbackTo` [option for service](Configuring.md#fallback-to) to help generate configuration
1. "Hello. I'm Mockintosh" in `x-mockintosh-prompt` header as sign of mock involved
1. use proper `async` style for Tornado functions
1. get rid of default config that runs with no params `mockintosh` command
1. ctrl+c to produce debug message only

## v0.7 - 2021-02-07

1. [Management API](Management.md) to get/set config, see stats, quick trying
1. [Performance/Chaos Profiles](Configuring.md#performancechaos-profiles)
1. [Tagging responses](Configuring.md#tagged-responses) of endpoint
1. referencing multipart/urlencoded fields in matchers and templates

## v0.6.2 - 2021-01-23

1. Series of bugfixes

## v0.6.1 - 2021-01-18

1. Document template helpers: random, dates, names, addresses etc
1. Better error reporting for wrong templates
1. Polish and document `faker` usage
1. Allow overriding port via env var `MOCKINTOSH_FORCE_PORT`

## v0.5.1 - 2021-01-13

1. Dataset support
1. SSL support
1. Ability to match request body by regexp
1. Counter functions
1. `random.*` templates
1. keep unsupported templates as-is
1. Support for running single service from config, selected by its comment
1. respond 400/405 if path matched, but method/header/qstr/body did not match
1. How do I do jsonPath extraction from request body?

## v0.4 - 2021-01-06

1. Automatic CORS
1. Ability to refer to external files containing request _and_ response bodies
    - make it secure by disallowing files outside mock config hierarchy
1. Clear status in log on which service addresses are listened to
    - right before `Mock server is ready!` have series of log lines
    - each line with clear URL of mock `Serving at http://<bind address>:port the mock for <service comment>`
1. have own server signature like `Mockintosh/<version>`
1. fix pip install
1. Multi-response functionality
1. Automatic image placeholders
1. allow specifying bind address via CLI option

## Milestone 4 - Complete

1. Integration of custom "interceptor"
    - Object model for request and response
    - Ability to provide python function/object to alter response
    - Both successful and failed responses intercepted

## Milestone 3 - Complete

1. Request headers and query string matching
2. Request JSON body schema validation as part of matching
3. Response status code
4. response headers - global and local

## Milestone 2 - Complete

1. Endpoints configuration with only Path matcher
2. Response with templating
4. Log exception if loading server failed

## Milestone 1 - Complete

1. Open Source project with documentation, examples, code quality, unit tests with coverage.
    - UP9 will do a lot of promotion for it, has to be good quality
1. CI process that tracks docker image size
2. Integration tests that run program/docker image and issue calls against it
3. setup.py, CLI
3. Multi-service engine
4. Config reading from file
    - consider JSON+YAML variants
5. No-config start with some default config
7. JSON Schema for configuration, validated for each config
6. Performance aspects kept in mind from the beginning
8. Extensibility aspects kept in mind from the very beginning
9. Logging with `-q` and `-v` respected

# Next Version

# Roadmap Ideas

## Async Mock Actors

- avro/grpc/binary/str problem in Kafka
- what to do with binary headers in Kafka? data-url prefix?
- interceptors to access kafka comms
- allow overriding on-demand producer fields via mgmt API
- trigger async produce via HTTP endpoint

- [https://github.com/jasonrbriggs/stomp.py](https://github.com/jasonrbriggs/stomp.py) - promises rabbitmq+activemq
- rabbitmq for async servers
- activemq for async servers
- mqtt for async servers
- SQS as one more async tech

## Management API/UI

- In unhandled tab, height: calc(100vh - 150px); does not work well when text is long
- upon navigating between mgmt UI tabs, refresh unhandled, stats
- config editor to provide hyperlinks from resource files into corresponding editing
- allow enabling multiple tags + allow response to trigger tag up/down => state machine for complex scenarios
- add API toggle to enable unhandled requests capture. Otherwise, we get OOMed easily.

## Other

- Tornado has auto-multicpu startup mode, use it optionally
- test the performance of ourself and optimize it


- support fragment same way we support query string - both in `path` and as standalone `fragment` option
- add support of array/list parameters on query strings like
  `/service2q?a=b&a=c` or `/service2q?a[]=b&a[]=c` and form data with multiple values for the same key to the request
  matching logic
- Nicer formatted error pages for known errors
- Nicer logging of requests, with special option to enable it.
- Import from OpenAPI and Postman collections `cat OpenAPI.json | mockintosh > mockintosh-config.yml`


- mocks for gRPC servers?
