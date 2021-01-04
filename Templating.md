Faker, random, request, counter

# Response Templating

Mockintosh uses syntax of [Handlebars](https://handlebarsjs.com/guide/) (default)
and [Jinja2](https://jinja.palletsprojects.com/en/2.11.x/) templating engines. To switch into Jinja2, use
the `templatingEngine` option of [configuration syntax](Configuring.md#advanced-templating-with-jinja2).

Any of the engine variants provides access to [Faker](https://faker.readthedocs.io/en/master/providers.html) library for
generating dynamic data.

## Response Fields

In response

### Status Code

The mock server supports both integer and string values for status code:

```yaml
endpoints:
  - path: /1
    response:
      status: 202
  - path: /2
    response:
      status: "404"
```

If the status code is not specified it defaults to `200`.

It is also possible to use templating in the `status` field like this:

```yaml
response:
  status: "{{someVar}}"
```

### Headers

One can define response headers specific to each individual endpoint like:

```yaml
response:
  body: 'hello world'
  status: 200
  headers:
    Cache-Control: no-cache
```

_Note: mind the [global headers](Configuring.md#global-settings) feature._

### Body

The body can be direct response string:

```yaml
response:
  body: 'hello world'
```

or a string that starts with `@` sign to indicate a separete template file:

```yaml
response:
  body: '@some/path/my_template.json.hbs'
```

The template file path is a relative path to the parent directory of the config file.

## Dynamic Values

### Request Object

The `request` object is exposed and can be used in places where the templating is possible. These are its attributes:

#### `request.version`

HTTP version e.g. `HTTP/1.1`, [see](https://tools.ietf.org/html/rfc2145).

#### `request.remoteIp`

The IP address of the client e.g. `127.0.0.1`.

#### `request.protocol`

The HTTP protocol e.g. `http` or `https`.

#### `request.host`

Full address of host e.g. `localhost:8001`.

#### `request.hostName`

Only the hostname e.g. `localhost`.

#### `request.uri`

URI, full path segments including the query string e.g. `/some/path?a=hello%20world&b=3`.

#### `request.method`

[HTTP methods](https://www.w3.org/Protocols/rfc2616/rfc2616-sec9.html). Supported verbs are:
`HEAD`, `GET`, `POST`, `DELETE`, `PATCH`, `PUT` and `OPTIONS`.

#### `request.path`

The path part of the URI e.g. `/some/path`.

#### `request.headers.<key>`

A request header e.g. `request.headers.accept` is `*/*`.

#### `request.queryString.<key>`

A query parameter e.g. `request.queryString.a` is `hello world`.

#### `request.body`

The raw request body as a whole. Can be `str`, `bytes` or `dict`.

#### `request.formData.<key>`

The `POST` parameters sent in a `application/x-www-form-urlencoded` request e.g. `request.formData.param1` is `value1`.

#### `request.files.<key>`

The fields in a `multipart/form-data` request.