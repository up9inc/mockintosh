# Changelog

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

# Roadmap

## Next Version
- YAML format for unhandled requests
- get rid of default config that runs with no params
- allow editing resource files via mgmt API/UI
- "Hello. I'm Mockintosh" in `x-mockintosh-prompt` header
- traffic log API & viewer

- mgmt UI change config global section didn't work
- Import from OpenAPI and Postman collections `cat OpenAPI.json | mockintosh > mockintosh-config.yml`
- "Bypass" mode for service to learn configuration
- report error in case config apply fails

- bug of applying status change via UI (Alon)
- \r vs \n problem in mac
- management UI to give links to individual services
- exp demo of requests log
- change config editor component
- don't clear traffic log on page reload

# Ideas

1. base64-encoded body strings, for binary responses
1. Content-Length that self-maintains, unless chunked transfer (default), some other magical HTTP protocol things (
   Accept etc)

- mocks for Kafka & RabbitMQ
  - https://github.com/spotify/docker-kafka - self-contained, maybe https://hub.docker.com/r/solsson/kafka/
  - on schedule producer
  - on demand producer
  - reactive consumer+producer
  - consumer fact validation
  - avro + grpc + JSON 
- mocks for gRPC servers

## Config Ideas

```json5
{
  "management": {
    // management API, allows to reload configs, get the stats etc
    "port": 9000
  },
  "performanceProfiles": {
    "profile1": {
      "ratio": 0.5,
      "delay": 1.5,
      // can be distributions
      "faults": {
        "RST": 0.1,
        "400": 0.1,
        "500": 0.1,
        "503": 0.1,
      }
    }
  },
  "globals": {
    "performanceProfile": "profile1",
    "headers": []
  },
  "services": [
    {
      // headers and performance profile per-service, maybe interceptors too
      // first service
      "name": "Mock for http://card-service.trdemo",
      "port": 8001,
      // optional per-service management API
      "managementRoot": "/__admin",
      "endpoints": [
        {
          "id": "unique id for endpoint",
          // "path": "/somepath/all/action",
          "path": "/somepath/{{regex '[^/]'}}/action",
          // "path": "/somepath/{{justval}}/action"
          // GET /somepath/1233423/action
          "headers": {
            "Content-Type": "application/json",
            "hname2": "{{regex '.+'}}"
          },
          "queryString": {
            "param1": "val1",
            "p2": "{{regex '.+'}}"
          },
          "body": {
            // regex criteria
            // "schema": "path/to/schemafile",
            "schema": {
              // inline schema
            }
          },
          "response": {
            "performanceProfile": "profile2",
            // "dataset": "path/to.csv",
            "dataset": [
              {
                "var1": "val1"
              },
              {
                "var1": "val2"
              }
            ],
            // "status": "{{random.int 200 500}}"
            "status": 200,
            "headers": [
              {
                "hname": "hval"
              },
              {
                "{{var1}}": "{{justval}}"
              }
            ],
            // "body": "simple {{time.now}} string"
            "body": {
              "useTemplating": true,
              "text": "",
              "fromFile": "",
              "modifications": [
                "{{jsonPath '$.path' 'value'}}"
                // somehow else?
              ]
            }
          },
        },
      ]
    },
    {
      // second service on different port
      "name": "Mock for http://frontend-service.trdemo",
      "port": 8002
    },
  ]
}
```

