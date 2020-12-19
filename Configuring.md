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
use in the response:

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

so that a request like `GET /parameterized/staticval/someval` would return *`static path segments have a high priority`*

#### Regex Match

With Mockintosh it's possible to use regular expression in path segments:

```yaml
- path: "/match/{{regEx 'prefix-.*'}}/someval"
  response: 'regex match: {{request.path}}'
```

so that a request like `GET /match/prefix-hello_world/someval` would
return `regex match: /match/prefix-hello_world/someval`

#### Regex Capture Group

It's also possible to use regular expression capture groups in path segments:

```yaml
- path: "/match/{{regEx 'prefix-(.*)' 'myVar'}}/someval"
  response: 'regex capture group: {{myVar}}'
```

so that a request like `GET /match/prefix-hello_world/someval` would return `regex capture group: hello_world`

You can use as many path parameter and regex capture groups you want:

```yaml
- path: "/parameterized5/text/{{var1}}/{{regEx 'prefix-(.*)-(.*)-suffix' 'var2' 'var3'}}/{{var4}}/{{regEx 'prefix2-(.*)' 'var5'}}"
  response: 'var1: {{var1}}, var2: {{var2}}, var3: {{var3}}, var4: {{var4}}, var5: {{var5}}'
```

## Response Contents