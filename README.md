# Chupeta, the API mocking server for microservice environments

## About

We respect the achievements of predecessors (Wiremock, Mockoon etc), we offer similar configuration syntax.

We aim for cloud-native/microservices, so the main case is many mocks running at once. Also, we aim for small Docker
image size, and small RAM requirement.

Today's services are all about performance, so we offer special features for performance/reliability testing
(see [this section](#performancechaos-profiles)).

## Config Example

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
      "faults": {
        "RST": 0.1,
        "400": 0.1,
        "500": 0.1,
        "503": 0.1,
      }
    }
  },
  "globals": {
    "requestInterceptors": [
      "mypackage.subpackage.myfunc"
    ],
    "performanceProfile": "profile1",
    "headers": []
  },
  "services": [
    {
      // first service
      "comment": "Mock for http://card-service.trdemo",
      "port": 8001,
      // optional per-service management API
      "managementRoot": "__admin",
      "endpoints": [
        {
          "path": "/somepath/{{regex '[^/]'}}/action",
          // "path": "/somepath/{{justval}}/action"

          "headers": {
            "Hname": "hval",
            "hname2": "{{regex '.+'}}"
          },
          "queryString": {
            "param1": "val1",
            "p2": "{{regex '.+'}}"
          },
          "body": {
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
            //"status": "{random.int 200 500}"
            "status": 200,
            "headers": [
              {
                "hname": "hval"
              },
              {
                "{{var1}}": "{{var2}}"
              }
            ],
            // "body": "simple string"
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
      "comment": "Mock for http://frontend-service.trdemo",
      "port": 8002
    },
  ]
}
```

## General

JSON+YAML config format

Ability to serve multiple services from single container, without much resource overhead

Have JSON schema for configuration language - avoid Mockoon’s mistake of not exposing the format enough

Import from OpenAPI and Postman collections

Ability to catch unhandled requests and turn those into configuration templates

Ability to get stats on mock items covered

JSON schema validation of request bodies (validation). Implicit validation through detailed response information.

## Stubbing

Ability to provide datasets for lists of possible values

Ability to refer to external files containing bodies (datasets?)

Ability to reference request parts in response - handlebars templating in wiremock and mockoon

Variants of responses based on rules

Sequences of responses

Ability to control a lot of response via request headers - for quick experimentation and code-level configuration in any
language

Content-Length that self-maintains, unless chunked transfer

## Management API

API to modify configuration remotely, maybe programmatically (for UP9 live control)
Global and per-service Allows to reload config on the fly Allows to get and reset the stats of the service Allows to
reset the cursors of datasets/performance profiles

## Performance/Chaos Profiles

Performance profile allows injecting faults and delays, round-robining the delays/500/400/RST, offering “profile ratio”
of fuzziness

## Extensibility

Object model for request and response Ability to provide python function/object to alter response Ability to provide
python function/object to access the request/response notifications

