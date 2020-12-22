# Mockintosh, the API mocking server for microservice environments

## About

Mockintosh aims to provide usual HTTP mock service functionality with small resource footprint, making it friendly for
microservice applications. You can have tens of mocks at once, inside moderate laptop or single Docker container. Also,
we have some additional ideas on how to make mocks simple and useful.

Key features:

- multiple services mocked by a single instance of Mockintosh
- lenient [configuration syntax](Configuring.md)
- performance testing supported

## Quick Start

If you have installed Mockintosh as Python package, start it with JSON/YAML [configuration file](Configuring.md) as
parameter:

```bash
mockintosh my_mocks.yaml
```

After server starts, you can issue requests against it.

Alternatively, you can run Mockintosh as Docker container:

```bash
docker run -it -p 8000-8005:8000-8005 -v `pwd`:/tmp mockintosh:latest /tmp/config.json
```
Please note the `-p` flag used to publish container ports and `-v` to mount directory with config into container.

---

## Build

Installing it directly:

```bash
pip3 install .
```

or as a Docker image:

```bash
docker build --no-cache -t mockintosh .
```

To verify the installation run `mockintosh` and visit [http://localhost:8001](http://localhost:8001)
you should be seeing the `hello world` response.

## Run

Running directly:

```bash
mockintosh tests/configs/json/hbs/common/config.json
```

or as a Docker container:

```bash
docker run -p 8000-8010:8000-8010 -v `pwd`/tests/configs/json/hbs/common/config.json mockintosh /config.json
# or
docker run --network host -v `pwd`/tests/configs/json/hbs/common/config.json mockintosh /config.json
```

### Command-line Arguments

The list of command-line arguments can be seen by running `mockintosh --help`.

If no configuration file is provided `mockintosh` starts with the default config shown below:

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

Mockintosh also supports piping config text into its `stdin` like:

```bash
cat tests/configs/json/hbs/common/config.json | mockintosh
```

`--debug` option enables Tornado Web Server's debug mode.

Using `--quiet` and `--verbose` options the logging level can be changed.

### Interceptors

One can also specify a list of interceptors to be called in `<package>.<module>.<function>` format using
the `--interceptor` option. The interceptor function get a [`mockintosh.Request`](#request-object) and
a [`mockintosh.Response`](#response-object) instance. Here is an example interceptor that for
every requests to a path starts with `/admin`, sets the reponse status code to `403`:

```python
import re

def forbid_admin(req: Request, resp: Response):
    if re.match(r'^\/admin.*$', req.path):
        resp.status = 403
```

and you would specify such interceptor with a command like below:

```bash
mockintosh some_config.json --interceptor=mypackage.mymodule.forbid_admin
```

Instead of specifying a package name, you can alternatively set the `PYTHONPATH` environment variable
to a directory that contains your interceptor modules like this:

```bash
PYTHONPATH=/some/dir mockintosh some_config.json --interceptor=mymodule.forbid_admin
```

#### Request Object

The `Request` object is exactly the same object defined in [here](Configuring.md#request-object)
with a minor difference: Instead of accesing the dictonary elements using `.<key>`,
you access them using `['<key>']` e.g. `request.queryString['a']`.

#### Response Object

The `Response` object consists of three fields:

##### Status

`resp.status` holds the [HTTP status codes](https://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html)
e.g. `200`, `201`, `302`, `404`, etc.

##### Headers

`resp.headers` is a Python dictionary that you access and/or modify the response headers.
e.g. `resp.headers['Cache-Control'] == 'no-cache'`

##### Body

The body can be anything that supported by [`tornado.web.RequestHandler.write`](https://www.tornadoweb.org/en/stable/web.html#tornado.web.RequestHandler.write)
Which means the body can be `str`, `bytes` or `dict` e.g. `resp.body = 'hello world'` or `resp.body = {'hello': 'world'}`
