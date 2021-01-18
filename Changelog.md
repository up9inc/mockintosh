# Changelog

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

## Milestone N

1. referencing multipart/urlencoded fields in matchers and templates
1. base64-encoded body strings, for binary responses
1. Import from OpenAPI and Postman collections
1. Content-Length that self-maintains, unless chunked transfer (default), some other magical HTTP protocol things (
   Accept etc)

## Milestone N

1. Management API
    - Ability to catch unhandled requests and turn those into configuration templates
    - Ability to get stats on mock items covered
    - API to modify configuration remotely, maybe programmatically (for UP9 live control)
    - Global and per-service (reuses same port)
    - Allows to reload config on the fly Allows to get and reset the stats of the service
    - Allows to reset the cursors of datasets/performance profiles
    - config retrieval
    - A way to attach OAS file to a server, so there is page in mgmt UI that opens `Try Now!` for this service.
      Automatically inject `servers` property of OAS.

1. Configuration-by-request
    - Ability to control a lot of response via request headers - for quick experimentation and code-level configuration
      in any language / maybe it falls into management API area

## Milestone N

1. Performance Profiles
    - Performance profile allows injecting faults and delays, round-robining the delays/500/400/RST, offering “profile
      ratio” of fuzziness

# Ideas

- `mockintosh --cli` to start interactive shell that would allow building the mock configuration interactively
- `cat OpenAPI.json | mockintosh > mockintosh-config.yml`
- mocks for gRPC servers
- mocks for Kafka

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

