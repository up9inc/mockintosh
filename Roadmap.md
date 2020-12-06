# Roadmap

## Milestone 1

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

## Milestone 2

1. Endpoints configuration with only Path matcher
2. Response with templating 
3. Content-Length that self-maintains, unless chunked transfer (default), some other magical HTTP protocol things 
   (Accept etc)

## Milestone 3

1. Request headers and query string
2. JSON body schema validation
3. urlencoded and multipart request bodies?

## Milestone 4

1. Multi-response functionality
1. Configuration-by-request
   - Ability to control a lot of response via request headers - for quick experimentation and code-level configuration in any
     language
1. Dataset support 
1. Ability to refer to external files containing request _and_ response bodies

## Milestone N

1. Management API
    - Ability to catch unhandled requests and turn those into configuration templates
    - Ability to get stats on mock items covered
    - API to modify configuration remotely, maybe programmatically (for UP9 live control)
    - Global and per-service (reuses same port)
    - Allows to reload config on the fly Allows to get and reset the stats of the service
    - Allows to reset the cursors of datasets/performance profiles
    - config retrieval

## Milestone N

1. Extensibility/integrations
    - Object model for request and response
    - Ability to provide python function/object to alter response
    - Ability to provide python function/object to access the request/response notifications

## Milestone N

1. Performance Profiles
    - Performance profile allows injecting faults and delays, round-robining the delays/500/400/RST, offering “profile
      ratio” of fuzziness

## Milestone N

1. Import from OpenAPI and Postman collections

# Backlog

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
      "delay": 1.5, // can be distributions
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
      // headers and performance profile per-service, maybe interceptors too
      // first service
      "comment": "Mock for http://card-service.trdemo",
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
          "body": { // regex criteria
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
      "comment": "Mock for http://frontend-service.trdemo",
      "port": 8002
    },
  ]
}
```

# Ideas

- `chupeta --cli` to start interactive shell that would allow building the mock configuration interactively
- `cat OpenAPI.json | chupeta > chupeta-config.yml`