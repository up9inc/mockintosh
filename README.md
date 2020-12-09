# Chupeta, the API mocking server for microservice environments

## About

We aim for cloud-native/microservices, so the main case is many mocks running at once. Also, we aim for small Docker
image size, and small RAM requirement.

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
docker build -t chupeta .
```

To verify the installation run `chupeta` and visit [http://localhost:8001](http://localhost:8001)
you should be seeing `{"hello": "world"}` response.

## Run

Running directly:

```bash
chupeta examples/template.j2
```

or as a Docker container:

```bash
docker run -p 8000-8010:8000-8010 -v `pwd`/tests/templates/template.json.j2:/template.json.j2 chupeta /template.json.j2
# or
docker run --network host -v `pwd`/tests/templates/template.json.j2:/template.json.j2 chupeta /template.json.j2
```

## The Mock Server Config

Chupeta supports both JSON and YAML formats as the mock server configuration file. Templating is possible using
[Jinja2](https://jinja.palletsprojects.com/en/2.11.x/) templating engine. Any of the standard provides of
[Faker](https://faker.readthedocs.io/en/master/providers.html) can also be used within the Jinja2 templates.

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
  - userId: {{ range(10000, 100000) | random }} # Random integer
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
          "response": {
            "hello": "world"
          }
        }
      ]
    }
  ]
}
```

`--debug` option enables Tornado Web Server's debug mode.

Using `--quiet` and `--verbose` options the logging level can be changed.
