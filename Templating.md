# Response Templating

Mockintosh uses syntax of [Handlebars](https://handlebarsjs.com/guide/) (default)
and [Jinja2](https://jinja.palletsprojects.com/en/2.11.x/) templating engines. To switch into Jinja2, use
the `templatingEngine` option of [configuration syntax](Configuring.md#advanced-templating-with-jinja2).

Any of the engine variants provides access to [Faker](https://faker.readthedocs.io/en/master/providers.html) library for
generating dynamic data.

## Response Fields

In response template, one can specify `status`, `headers` and `body` of HTTP message. Here's quick example:

```yaml
services:
  - port: 8080
    endpoints:
      - path: /api-call
        response:
          status: 201
          headers:
            content-type: application/json
            x-custom-id: 12345
          body: '{"result": "created"}'            
```

Any of those fields allows using dynamic template that will be evaluated for each request. Like this:

```yaml
services:
  - port: 8080
    endpoints:
      - path: /api-call
        response:
          status: "{{request.queryString.rc}}"
          headers:
            content-type: '{{request.headers.accept}}'
            x-custom-id: '{{random.int 0 1000}}'
          body: '{"result": "created", "name": "{{fake.lastname}}" }'            
```

_Note: for `headers`, only the value part is subject for templating. Mind
the [global headers](Configuring.md#global-settings) feature, too._

The `body` can be direct response string:

```yaml
response:
  body: 'hello world'
```

or a string that starts with `@` sign to indicate a file on disk:

```yaml
response:
  body: '@some/path/my_template.json.hbs'
```

_Note: The template file path has to be relative to the directory of the config file._

## Dynamic Values

By default, dynamic templates use Handlebars syntax and look like this: `{{namedVal}}` or `{{request.path}}` or `{{fake.address}}` etc. 

TODO: Can I use nested expressions?

Below are 

### Random

- uuid4
- integers with range
- float 0..1 with desired precision
- string of desired len

For random names, addresses etc, please refer to [Faker's](#faker) functionality.

### Faker

_reference of available_

### Counters

Named counters

### Request Object

The `request` object is exposed and can be used in places where the templating is possible. These are the most useful
attributes:

- `request.path` - The path part of the URI e.g. `/some/path`.
- `request.path.<n>` - The specific component part of the URI
- `request.headers.<key>` - A request header e.g. `request.headers.accept`.
- `request.queryString.<key>` - A query parameter e.g. `request.queryString.a` is `hello world`.
- `request.body` - The raw request body as a whole. Can be `str`, `bytes` or `dict`.
- `request.formData.<key>` - The `POST` parameters sent in a `application/x-www-form-urlencoded` request
  e.g. `request.formData.param1` is `value1`.
- `request.files.<key>` - The fields in a `multipart/form-data` request.

Less frequently used:

- `request.method` - [HTTP method](https://www.w3.org/Protocols/rfc2616/rfc2616-sec9.html)
- `request.uri` - URI, full path segments including the query string e.g. `/some/path?a=hello%20world&b=3`.
- `request.host` - Full address of host e.g. `localhost:8001`.
- `request.hostName` - Only the hostname e.g. `localhost`.
- `request.protocol` - The HTTP protocol e.g. `http` or `https`.
- `request.remoteIp` - The IP address of the client e.g. `127.0.0.1`.
- `request.version` - HTTP version e.g. `HTTP/1.1`, [see](https://tools.ietf.org/html/rfc2145).





