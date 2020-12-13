# Chupeta, the API mocking server for microservice environments

## About

We aim for cloud-native/microservices, so the main case is many mocks running at once. Also, we aim for small Docker
image size, and less memory requirement.

Today's services are all about performance, so we offer special features for performance/reliability testing
(see [this section](#performancechaos-profiles)).

We respect the achievements of predecessors (Wiremock, Mockoon etc), we offer similar configuration syntax.

## Build

Installing it directly:

```bash
pip3 install .
```

or as a Docker image:

```bash
docker build --no-cache -t chupeta .
```

To verify the installation run `chupeta` and visit [http://localhost:8001](http://localhost:8001)
you should be seeing the `hello world` response.

## Run

Running directly:

```bash
chupeta tests/configs/json/hbs/common/config.json
```

or as a Docker container:

```bash
docker run -p 8000-8010:8000-8010 -v `pwd`/tests/configs/json/hbs/common/config.json chupeta /config.json
# or
docker run --network host -v `pwd`/tests/configs/json/hbs/common/config.json chupeta /config.json
```

# The Mock Server Config

Chupeta supports both JSON and YAML formats as the mock server configuration file. Templating is also possible using
[Handlebars](https://handlebarsjs.com/guide/) (default) and [Jinja2](https://jinja.palletsprojects.com/en/2.11.x/)
templating engines. Any of the standard provides of [Faker](https://faker.readthedocs.io/en/master/providers.html)
can also be used within the Handlebars or Jinja2 templates.

You can specifiy the templating engine on top of the file like `templatingEngine: "Jinja2"` or inside and response.

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
  {% for n in range(5) %} # 0-5 random length of users will be mocked
  - id: {{ range(10000, 100000) | random }} # Random integer
    firstName: '{{ fake.first_name() }}' # Fake first name
    lastName: '{{ fake.last_name() }}' # Fake last name
    friends: # List of user's friends
    {% for n in range(range(5) | random) %} # 0-5 random length of user ids will be mocked
    - id: '{{ uuid() }}' # Random UUID
    {% endfor %}
  {% endfor %}
  total: 10 # Total number of users
```

## Command-line Arguments

The list of command-line arguments can be seen by running `chupeta --help`.

If no configuration file is provided `chupeta` starts with the default config shown below:

```json
{
  "services": [
    {
      "comment": "Default Mock Service Config",
      "hostname": "localhost",
      "port": 8001,
      "endpoints": [
        {
          "path": "/",
          "method": "GET",
          "response": "hello world"
        }
      ]
    }
  ]
}
```

Chupeta also supports piping config text into its `stdin` like:

```bash
cat tests/configs/json/hbs/common/config.json | chupeta
```

`--debug` option enables Tornado Web Server's debug mode.

Using `--quiet` and `--verbose` options the logging level can be changed.


## Request

### Path

#### Path Parameters

You can use `{{varname}}` syntax to specify a path parameter in any segment of your paths and they will be
available for use in the response:

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

With Chupeta it's possible to use regular expression in path segments:

```yaml
- path: "/match/{{regEx 'prefix-.*'}}/someval"
  response: 'regex match: {{request.path}}'
```

so that a request like `GET /match/prefix-hello_world/someval` would return `regex match: /match/prefix-hello_world/someval`

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
