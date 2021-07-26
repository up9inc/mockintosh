# Mockintosh

<p align="center">
    <a href="https://github.com/up9inc/mockintosh/releases/latest">
        <img alt="GitHub Latest Release" src="https://img.shields.io/github/v/release/up9inc/mockintosh?logo=GitHub&style=flat-square">
    </a>
    <a href="https://github.com/up9inc/mockintosh/blob/master/LICENSE">
        <img alt="GitHub License" src="https://img.shields.io/github/license/up9inc/mockintosh?logo=GitHub&style=flat-square">
    </a>
    <a href="https://travis-ci.com/github/up9inc/mockintosh/builds/">
        <img alt="Travis" src="https://img.shields.io/travis/up9inc/mockintosh?logo=Travis&style=flat-square">
    </a>
    <a href="https://hub.docker.com/r/up9inc/mockintosh">
        <img alt="Docker Build Status" src="https://img.shields.io/docker/cloud/build/up9inc/mockintosh?logo=Docker&style=flat-square">
    </a>
    <a href="https://codecov.io/gh/up9inc/mockintosh">
        <img alt="Code Coverage (Codecov)" src="https://img.shields.io/codecov/c/github/up9inc/mockintosh?logo=Codecov&style=flat-square">
    </a>
</p>

You've just found a new way of mocking microservices!

![Control Plane](https://i.ibb.co/3kG9xMr/Screenshot-from-2021-07-07-12-53-40.png)

An example config that demonstrates the common features of Mockintosh:

```yaml
templatingEngine: Jinja2
services:
- name: Mock for Service1
  hostname: localhost
  port: 8001
  managementRoot: __admin
  endpoints:
  - path: "/"
    method: GET
    response:
      headers:
        Content-Type: "text/html; charset=UTF-8"
      body: "@templates/index.html.j2"
  - path: "/users"
    method: GET
    response:
      headers:
        Content-Type: "application/json; charset=UTF-8"
      body: "@templates/users.json.j2"
- name: Mock for Service2
  hostname: service2.example.com
  port: 8002
  endpoints:
  - path: "/companies"
    method: POST
    body:
      schema:
        type: object
        properties:
          name:
            type: string
          address:
            type: string
        required:
        - name
        - address
    response:
      headers:
        Content-Type: "application/json; charset=UTF-8"
      body: "@templates/company.json.j2"
```

Mockintosh is a service virtualization tool that's capable to generate mocks for **RESTful APIs** and communicate with **message queues**
to either mimic **asyncronous** tasks or to simulate **microservice architectures** in a blink of an eye.

The state-of-the-art mocking capabilities of Mockintosh enables software development teams to work
**independently** while building and maintaining a **complicated** microservice architecture.

Key features:

- Multiple services mocked by a single instance of Mockintosh
- Lenient [configuration syntax](Configuring.md)
- Request scenarios support with [multi-response endpoints](Configuring.md#multiple-responses)
- Performance testing supported (with [datasets](Configuring.md#datasets) and low resource footprint)
- [Interceptors](#interceptors) support for unlimited customization
- Remote [management UI+API](Management.md)

_[In this article](https://up9.com/open-source-microservice-mocking-introducing-mockintosh) we explain how and why Mockintosh has born as a new way of mocking microservices._

## Quick Start

Install Mockintosh Python package using [`pip`](https://pypi.org/project/pip/):

```shell
$ pip install mockintosh
```

Once the installation complete, you can start Mockintosh with a JSON/YAML configuration as an
argument, e.g. [example.yaml](docs/examples/example.yaml):

```shell
$ mockintosh example.yaml
```

and you should be seeing a web page like this whenever you visit [localhost:8001](http://localhost:8001):

![HTML Templating Example](https://i.ibb.co/PcjBNGF/Screenshot-from-2021-07-07-14-08-26.png)

Alternatively, you can run Mockintosh as Docker container:

```shell
$ docker run -it -p 8000-8005:8000-8005 -v `pwd`:/tmp up9inc/mockintosh /tmp/config.json
```

Please note the `-p` flag used to publish container's ports and `-v` to mount directory with config into container.

After server starts, you can issue requests against it. For example, `curl -v http://localhost:8000/` would
respond `hello world`. Also, consider opening [Management UI](Management.md) in your
browser: [http://localhost:8000/__admin](http://localhost:8000/__admin). Management UI offers visual tools to see available mock endpoints, traffic log
and many other [features](Management.md).

## Command-line Arguments

The list of command-line arguments can be seen by running `mockintosh --help`.

If you don't want to listen all of the services in a configuration file then you can specify a list of service
names (`name` is a string attribute you can set per service):

```shell
$ mockintosh example.yaml 'Mock for Service1' 'Mock for Service2'
```

Using `--quiet` and `--verbose` options the logging level can be changed.

Using `--bind` option the bind address for the mock server can be specified, e.g. `mockintosh --bind 0.0.0.0`

Using `--enable-tags` option the tags in the configuration file can be
enabled in startup time, e.g. `mockintosh --enable-tags first,second`

### OpenAPI Specification to Mockintosh Config Conversion (_experimental_)

_Note: This feature is experimental. One-to-one transpilation of OAS documents is not guaranteed._

It could be a good kickstart if you have already an OpenAPI Specification for your API.
Mockintosh is able to transpile an OpenAPI Specification to its own config format in two different ways:

#### CLI Option `--convert`

Using the `--convert` one can convert an OpenAPI Specification to Mockintosh config.

JSON output example:

```shell
$ wget https://petstore.swagger.io/v2/swagger.json
$ mockintosh swagger.json -c new_config.json json
```

YAML example:

```shell
$ mockintosh swagger.json -c new_config.yaml yaml
```

#### Automatic Conversion

If you start Mockintosh with a valid OpenAPI Specification file then it automatically detects that the input
is an OpenAPI Specification file:

```shell
$ mockintosh swagger.json
```

and automatically starts itself from that file. Without producing any new files. So you can start to edit this file
through the management UI without even restarting Mockintosh.

## Interceptors

One can also specify a list of interceptors to be called in `<package>.<module>.<function>` format using
the `--interceptor` option. The interceptor function get a [`mockintosh.Request`](#request-object) and
a [`mockintosh.Response`](#response-object) instance. Here is an example interceptor that for every requests to a path
starts with `/admin`, sets the reponse status code to `403`:

```python
import re
from mockintosh import Request, Response


def forbid_admin(req: Request, resp: Response):
    if re.search(r'^\/admin.*$', req.path):
        resp.status = 403
```

and you would specify such interceptor with a command like below:

```shell
$ mockintosh some_config.json --interceptor=mypackage.mymodule.forbid_admin
```

Instead of specifying a package name, you can alternatively set the `PYTHONPATH` environment variable to a directory
that contains your interceptor modules like this:

```shell
$ PYTHONPATH=/some/dir mockintosh some_config.json --interceptor=mymodule.forbid_admin
```

_Note: With interceptors, you can even omit `endpoints` section from the service config. You will still get all requests
to the service into your interceptor._

### Request Object

The `Request` object is exactly the same object defined in [here](Templating.md#request-object)
with a minor difference: Instead of accesing the dictonary elements using `.<key>`, you access them using `['<key>']`
e.g. `request.queryString['a']`.

### Response Object

The `Response` object consists of three fields:

- `resp.status` holds the [HTTP status codes](https://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html)
  e.g. `200`, `201`, `302`, `404`, etc.
- `resp.headers` is a Python dictionary that you access and/or modify the response headers.
  e.g. `resp.headers['Cache-Control'] == 'no-cache'`
- `resp.body` is usually either `str` or `bytes`, but can be anything that is supported
  by [`tornado.web.RequestHandler.write`](https://www.tornadoweb.org/en/stable/web.html#tornado.web.RequestHandler.write)
  : `str`, `bytes` or `dict` e.g. `resp.body = 'hello world'`
  or `resp.body = {'hello': 'world'}`

### Build the Docs

Install [Jekyll](https://jekyllrb.com/) and [Bundler](https://bundler.io/):

```shell
$ gem install jekyll bundler
```

Install the gems:

```shell
$ cd docs/
$ bundle config set --local path 'vendor/bundle'
$ bundle install
```

Run the server:

```shell
$ bundle exec jekyll serve
```

### Useful Links

[**Documentation Website**](https://mockintosh.io/)

[**YouTube Video Series**](https://www.youtube.com/watch?v=Q8RPT6TPOIg&list=PLJE3O0IuP-IZMWEOI8dU0U3rO_CPPhLv9)

[**Bug Tracker**](https://github.com/up9inc/mockintosh/issues)

[**Slack**](https://up9.slack.com/)

[**Stack Overflow**](https://stackoverflow.com/questions/tagged/mockintosh)

[**Faker API Reference**](https://faker.readthedocs.io/en/master/providers.html)
