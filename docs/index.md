# Mockintosh

## About

Mockintosh aims to provide usual HTTP mock service functionality with small resource footprint, making it friendly for
microservice applications. You can have tens of mocks at once, inside moderate laptop or single Docker container. Also,
we have some additional ideas on how to make mocks simple and useful.

Key features:

- multiple services mocked by a single instance of Mockintosh
- lenient [configuration syntax](Configuring.md)
- request scenarios support with [multi-response endpoints](Configuring.md#multiple-responses)
- performance testing supported (with [datasets](Configuring.md#datasets) and low resource footprint)
- [interceptors](#interceptors) support for unlimited customization
- remote [management UI+API](Management.md)

_Note: There is an [article on UP9 blog](https://up9.com/open-source-microservice-mocking-introducing-mockintosh) explaining motivation behind Mockintosh project._

## Quick Start

```shell
pip3 install mockintosh
```

If you have installed Mockintosh as Python package (requires Python 3.x+), start it with JSON/YAML configuration as an
argument (consider [my_mocks.yaml](examples/my_mocks.yaml) as example):

```shell
mockintosh my_mocks.yaml
```

Alternatively, you can run Mockintosh as Docker container:

```bash
docker run -it -p 8000-8005:8000-8005 -v `pwd`:/tmp up9inc/mockintosh /tmp/config.json
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
mockintosh my_mocks.yaml 'Mock for Service1' 'Mock for Service2'
```

Using `--quiet` and `--verbose` options the logging level can be changed.

Using `--bind` option the bind address for the mock server can be specified, e.g. `mockintosh --bind 0.0.0.0`

Using `--enable-tags` option the tags in the configuration file can be
enabled in startup time, e.g. `mockintosh --enable-tags first,second`

### OpenAPI Specification to Mockintosh Config Conversion

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

If you start Mockintosh with a valid OpenAPI Specification file then it automatically dumps a `config.yaml`
to your current working directory:

```shell
$ mockintosh swagger.json
$ cat config.yaml
```

and automatically starts itself from that `config.yaml` file. So you can start to edit this file
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

```bash
mockintosh some_config.json --interceptor=mypackage.mymodule.forbid_admin
```

Instead of specifying a package name, you can alternatively set the `PYTHONPATH` environment variable to a directory
that contains your interceptor modules like this:

```bash
PYTHONPATH=/some/dir mockintosh some_config.json --interceptor=mymodule.forbid_admin
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
