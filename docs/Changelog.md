# Changelog

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

TODO:

- mocks for Kafka & RabbitMQ
    - on schedule producer
    - on demand producer
    - reactive consumer+producer
    - consumer fact validation
    - global headers considered
    - avro + grpc + JSON
    - what to do with binary headers?
    - bodies from file
    - traffic log to display kafka comms
    - interceptors to access kafka comms
    - stats to count kafka comms
    - allow overriding on-demand producer fields via mgmt API
    - config reloading to work

1. Display timestamps in traffic log
1. Do not respond with Content-Type=text/html if no content-type header is configured

# Roadmap Ideas

- support fragment same way we support query string - both in `path` and as standalone `fragment` option
- cli argument to set the tag
- add support of array/list parameters on query strings like
  `/service2q?a=b&a=c` or `/service2q?a[]=b&a[]=c` and form data with multiple values for the same key to the request
  matching logic
- Nicer formatted error pages for known errors
- Nicer debug logging of requests
- admin UI to show available tags and allow switching
- Import from OpenAPI and Postman collections `cat OpenAPI.json | mockintosh > mockintosh-config.yml`
- config editor to provide hyperlinks from resource files into corresponding editing

1. base64-encoded body strings, for binary responses
1. Content-Length that self-maintains, unless chunked transfer (default), some other magical HTTP protocol things (
   Accept etc)

- SQS as one more async tech

- mocks for gRPC servers
