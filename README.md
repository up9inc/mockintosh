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

## Quick Links

[**Documentation Website**](https://mockintosh.io/)

[**YouTube Video Series**](https://www.youtube.com/watch?v=Q8RPT6TPOIg&list=PLJE3O0IuP-IZMWEOI8dU0U3rO_CPPhLv9)

[**Bug Tracker**](https://github.com/up9inc/mockintosh/issues)

[**Slack**](https://up9.slack.com/)

[**Stack Overflow**](https://stackoverflow.com/questions/tagged/mockintosh)

[**Faker API Reference**](https://faker.readthedocs.io/en/master/providers.html)

## About

You've just found a new way of mocking microservices!

![Control Plane](https://i.ibb.co/3kG9xMr/Screenshot-from-2021-07-07-12-53-40.png)

An example config that demonstrates the common features of Mockintosh:

```yaml
services:
  - name: Mock for Service1
    hostname: localhost
    port: 8000
    managementRoot: __admin  # open http://localhost:8001/__admin it in browser to see the UI  
    endpoints:

      - path: "/"  # simplest mock

      - path: "/api/users/{{param}}"  # parameterized URLs
        response: "simple string response with {{param}} included"

      - path: /comprehensive-matching-and-response
        method: POST
        queryString:
          qName1: qValue  # will only match if query string parameter exists
          qName2: "{{regEx '\\d+'}}"  # will require numeric value
        headers:
          x-required-header: someval  # will cause only requests with specific header to work
        body:
          text: "{{regEx '.+'}}"  # will require non-empty POST body
        response: # the mocked response specification goes below
          status: 202
          body: "It worked"
          headers:
            x-response-header: "{{random.uuid4}}"  # a selection of random/dynamic functions is available
            x-query-string-value: "{{request.queryString.qName2}}"  # request parts can be referenced in response

```

Mockintosh is a service virtualization tool that's capable to generate mocks for **RESTful APIs** and communicate
with **message queues**
to either mimic **asynchronous** tasks or to simulate **microservice architectures** in a blink of an eye.

The state-of-the-art mocking capabilities of Mockintosh enables software development teams to work
**independently** while building and maintaining a **complicated** microservice architecture.

Key features:

- Multiple services mocked by a single instance of Mockintosh
- Lenient [configuration syntax](https://mockintosh.io/Configuring.html)
- Remote [management UI+API](https://mockintosh.io/Management.html)
- Request scenarios support with [multi-response endpoints](https://mockintosh.io/Configuring.html#multiple-responses)
  and [tags](https://mockintosh.io/Configuring.html#tagged-responses)
- [Mock Actor](https://mockintosh.io/Async.html) pattern for Kafka, RabbitMQ, Redis and some other message bus protocols
- GraphQL queries recognizing

_[In this article](https://up9.com/open-source-microservice-mocking-introducing-mockintosh) we explain how and why
Mockintosh was born as a new way of mocking microservices._

## Quick Start

### Install on MacOS

Install Mockintosh app on Mac using [Homebrew](https://brew.sh/) package manager:

```shell
$ brew install up9inc/repo/mockintosh
```
### Install on Windows

Download an installer from [releases](https://github.com/up9inc/mockintosh/releases) section and launch it. Follow the steps in wizard to install Mockintosh.

### Install on Linux

Install Mockintosh Python package using [`pip`](https://pypi.org/project/pip/) (or `pip3` on some machines):

```shell
$ pip install -U mockintosh
```

### Use Demo Sample Config

Run following command to generate `example.yaml` file in the current directory:

```shell
$ mockintosh --sample-config example.yaml
```

then, run that config with Mockintosh:

```shell
$ mockintosh example.yaml
```

And open http://localhost:9999 in your web browser.

You can also issue some CURL requests against it:

```shell
curl -v http://localhost:8888/

curl -v http://localhost:8888/api/myURLParamValue123/action

curl -v "http://localhost:8888/someMoreFields?qName1=qValue&qName2=12345" -X POST -H"X-Required-Header: someval" --data "payload"
```

## Command-line Arguments

The list of command-line arguments can be seen by running `mockintosh --help`.

If you don't want to listen all of the services in a configuration file then you can specify a list of service
names (`name` is a string attribute you can set per service):

```shell
$ mockintosh example.yaml 'Mock for Service1' 'Mock for Service2'
```

Using `--quiet` and `--verbose` options the logging level can be changed.

Using `--bind` option the bind address for the mock server can be specified, e.g. `mockintosh --bind 0.0.0.0`

Using `--enable-tags` option the tags in the configuration file can be enabled in startup time,
e.g. `mockintosh --enable-tags first,second`

## OpenAPI Specification to Mockintosh Config Conversion (_experimental_)

_Note: This feature is experimental. One-to-one transpilation of OAS documents is not guaranteed._

It could be a good kickstart if you have already an OpenAPI Specification for your API. Mockintosh is able to transpile
an OpenAPI Specification to its own config format in two different ways:

### CLI Option `--convert`

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

### Automatic Conversion

If you start Mockintosh with a valid OpenAPI Specification file then it automatically detects that the input is an
OpenAPI Specification file:

```shell
$ mockintosh swagger.json
```

and automatically starts itself from that file. Without producing any new files. So you can start to edit this file
through the management UI without even restarting Mockintosh.

## Build the Docs

Single-command from `/docs` to review docs locally:
```shell
docker run -p 8080:4000 -v $(pwd):/site bretfisher/jekyll-serve
```

Or manual:

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

