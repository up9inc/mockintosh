# The Mock Server Config

Mockintosh supports both JSON and YAML formats as the mock server configuration file. Templating is also possible using
[Handlebars](https://handlebarsjs.com/guide/) (default) and [Jinja2](https://jinja.palletsprojects.com/en/2.11.x/)
templating engines. Any of the standards provides access
to [Faker](https://faker.readthedocs.io/en/master/providers.html) library for generating dynamic data.

There is a [JSONSchema of configuration syntax](https://github.com/up9inc/mockintosh/blob/main/mockintosh/schema.json) that is used to validate all configuration files. You can use that as a formal source of configuration syntax.

You can specifiy the templating engine on top of the file like `templatingEngine: "Jinja2"` or inside the response.

The configuration file should contain the list of definitions of your microservices like shown below:

```yaml
services: # List of your microservices
  - comment: "Mock for http://example1.com" # Comment related to the service that will be logged
    hostname: "service1.example.com" # Hostname of the service (defaults to "localhost")
    port: 8001 # The port of the service
    endpoints: ... # Endpoints
  - comment: "Mock for http://example2.com"
    hostname: "service2.example.com"
    port: 8002
    endpoints: ...
```

*Note: It's also possible to not define the `hostname`. In that case the service occupies the whole port*
*alternatively, one can define two service with different hostnames on the same port number.*

The fields of an endpoint is shown below:

```yaml
endpoints: # List of the endpoints in your microservice
  - path: "/users" # Path of the endpoint
    method: GET # The HTTP verb
    response: .. # Response
```

A response example that leverages Jinja2 templating and Faker is shown below:

```yaml
response: # Response of the endpoint
  users: # A list of mocked user data
  { % for n in range(5) % } # 0-5 random length of users will be mocked
  - id: { { range(10000, 100000) | random } } # Random integer
    firstName: '{{ fake.first_name() }}' # Fake first name
    lastName: '{{ fake.last_name() }}' # Fake last name
    friends: # List of user's friends
    { % for n in range(range(5) | random) % } # 0-5 random length of user ids will be mocked
    - id: '{{ uuid() }}' # Random UUID
    { % endfor % }
  { % endfor % }
  total: 10 # Total number of users
```

## Request Matching Logic

### Path

#### Path Parameters

You can use `{{varname}}` syntax to specify a path parameter in any segment of your paths and they will be available for
using in the response:

```yaml
endpoints:
  - path: "/parameterized/{{myVar}}/someval"
    response: 'Here is: {{myVar}}'
```

#### Static Value Priority

Even if you specified a path parameter for a certain path segment, static values have a high priority:

```yaml
endpoints:
  - path: "/parameterized/{{myVar}}/someval"
    response: 'Here is: {{myVar}}'
  - path: "/parameterized/staticval/someval"
    response: static path segments have a high priority
```

so that a request like `curl -X GET http://localhost:8001/parameterized/staticval/someval` would return *`static path segments have a high priority`*

#### Regex Match

With Mockintosh it's possible to use regular expressions in path segments:

```yaml
- path: "/match/{{regEx 'prefix-.*'}}/someval"
  response: 'regex match: {{request.path}}'
```

so that a request like `curl -X GET http://localhost:8001/match/prefix-hello_world/someval` would
return `regex match: /match/prefix-hello_world/someval`

#### Regex Capture Group

It's also possible to use regular expression capture groups in path segments:

```yaml
- path: "/match/{{regEx 'prefix-(.*)' 'myVar'}}/someval"
  response: 'regex capture group: {{myVar}}'
```

so that a request like `curl -X GET http://localhost:8001/match/prefix-hello_world/someval` would return `regex capture group: hello_world`

You can use as many path parameter and regex capture groups you want:

```yaml
- path: "/parameterized5/text/{{var1}}/{{regEx 'prefix-(.*)-(.*)-suffix' 'var2' 'var3'}}/{{var4}}/{{regEx 'prefix2-(.*)' 'var5'}}"
  response: 'var1: {{var1}}, var2: {{var2}}, var3: {{var3}}, var4: {{var4}}, var5: {{var5}}'
```

### Headers

Any header specified in the endpoint description is required to be exist in the request headers. Otherwise the mock
server will look for other alternatives of with the exact path and HTTP method combination. If not match is found
a `404` response will be returned. Here is an example configuration which demonstrates the how endpoint alternatives
recognized in terms of headers:

```yaml
services:
- comment: Service1
  port: 8001
  endpoints:
  - path: "/alternative"
    method: GET
    headers:
      hdr1: myValue
      hdr2: "{{myVar}}"
      hdr3: "{{regEx 'prefix-(.+)-suffix' 'myCapturedVar'}}"
    response:
      body: 'headers match: {{request.headers.hdr1}} {{myVar}} {{myCapturedVar}}'
      status: 201
      headers:
        Set-Cookie:
        - name1={{request.headers.hdr2}}
        - name2={{request.headers.hdr3}}
  - path: "/alternative"
    headers:
      hdr4: another header
    response:
      body: 'hdr4 request header: {{request.headers.hdr4}}'
      headers:
        hdr4: 'hdr4 request header: {{request.headers.hdr4}}'
```

For the above configuration example here are some example requests and their responses:

- Request: `curl -X GET http://localhost:8001/alternative -H "hdr1: wrongValue"` Response: `404`
- Request: `curl -X GET http://localhost:8001/alternative -H "hdr1: myValue" -H "hdr2: someValue"` Response: `404`
- Request: `curl -X GET http://localhost:8001/alternative -H "hdr1: myValue" -H "hdr2: someValue" -H "hdr3: prefix-invalidCapture"` Response: `404`
- Request: `curl -X GET http://localhost:8001/alternative -H "hdr1: myValue" -H "hdr2: someValue" -H "hdr3: prefix-validCapture-suffix"` Response: `201` - `headers match: mvValue someValue validCapture` (also it sets the cookies `name1` to `someValue` and `name2` to `validCapture`)
- Request: `curl -X GET http://localhost:8001/alternative -H "hdr4: another header"` Response: `200` - `hdr4 request header: another header`
- Request: `curl -X GET http://localhost:8001/alternative -H "hdr5: another header"` Response: `404`

As you can understand from these request and response examples; the workflow of static values, parameters,
regex match and regex capture groups, is exactly the same with how they works in [path](###Path).

### Query String

The matching logic for query strings is quite similar to [headers](###Headers). So here is the same example but
in terms of the query strings:

```yaml
services:
- comment: Service1
  port: 8001
  - path: "/alternative"
    method: GET
    queryString:
      param1: my Value
      param2: "{{myVar}}"
      param3: "{{regEx 'prefix-(.+)-suffix' 'myCapturedVar'}}"
    response:
      body: 'query string match: {{request.queryString.param1}} {{myVar}} {{myCapturedVar}}'
      status: 201
  - path: "/alternative"
    queryString:
      param4: another query string
    response:
      body: 'param4 request query string: {{request.queryString.param4}}'
```

and these are the example requests and corresponding responses for such a mock server configuration:

- Request: `curl -X GET http://localhost:8001/alternative?param1=wrongValue"` Response: `404`
- Request: `curl -X GET http://localhost:8001/alternative?param1=my%20Value&param2=someValue"` Response: `404`
- Request: `curl -X GET http://localhost:8001/alternative?param1=my%20Value&param2=someValue&param3=prefix-invalidCapture"` Response: `404`
- Request: `curl -X GET http://localhost:8001/alternative?param1=my%20Value&param2=someValue&param3=prefix-validCapture-suffix"` Response: `201` - `query string match: mvValue someValue validCapture`
- Request: `curl -X GET http://localhost:8001/alternative?param4=another%20query%20string"` Response: `200` - `param4 request query string: another query string`
- Request: `curl -X GET http://localhost:8001/alternative?param5=another%20query%20string"` Response: `404`

### JSON Body Schema Validation

The mock server supports [JSON Schema](https://json-schema.org/) specification as matching logic. Consider this example:

```yaml
---
services:
- comment: Mock for Service1
  port: 8001
  endpoints:
  - path: "/endpoint1"
    method: POST
    body:
      schema:
        type: object
        properties:
          somekey: {}
        required:
        - somekey
    response: 'endpoint1: body JSON schema matched'
```

and here is a two request example that one matches the JSON schema while the other doesn't match:

- Request:

```bash
curl -X POST http://localhost:8001/endpoint1?param1=wrongValue \
     -H "Accept: application/json"
     -d '{"somekey": "valid"}'
```

Response: `200` - `endpoint1: body JSON schema matched`

- Request:

```bash
curl -X POST http://localhost:8001/endpoint1?param1=wrongValue \
     -H "Accept: application/json"
     -d '{"somekey2": "invalid"}'
```

Response: `404`

## Response Contents

### Status Code

The mock server supports both integer:

```yaml
response:
  status: 202
```

and string values:

```yaml
response:
  status: '403'
```

as the status code in the response definition.

It's also possible to use templating in the `status` field like this:

```yaml
response:
  status: "{{someVar}}"
```

### Headers

#### Local

One can define response headers specific to each individual endpoint like:

```yaml
response:
  body: 'hello world'
  status: 200
  headers:
    Cache-Control: no-cache
```

#### Local

It's also possible to define response headers in global level. Such that each endpoint will include those headers into
their responses:

```yaml
globals:
  headers:
    Content-Type: application/json
...
      response:
        body: 'hello world'
        status: 200
        headers:
          Cache-Control: no-cache
```

### Request Object

The `request` object is exposed and can be used in places where the templating is possible. These are its attributes:

```text
request.method
request.path
request.headers.<key>
request.queryString.<key>
```
