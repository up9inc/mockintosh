# Configuration Syntax

Mockintosh supports JSON and YAML formats for the mock server configuration file.

The most important entities in the config file are: Service, Endpoint, Response:

![Config](MockintoshConfig.png)

There are two main aspects of endpoint configuration: matching and templating. [Matching](Matching.md) defines how to
recognize request and pick the corresponding response template. [Templating](Templating.md) gives capabilities to
configure different response fields, and also make responses to be dynamic.

_Note: There is
a [JSONSchema of configuration syntax](https://github.com/up9inc/mockintosh/blob/main/mockintosh/schema.json)
that is used to validate all configuration files. You can use that as a formal source of configuration syntax._

## Defining Services

When defining services, the key property is `port`, which defines on which port the server will be available to
requests. It is also a good practice to specify `comment` property. You can configure one or multiple services at once.
Here's a minimalistic working example:

```yaml
services:
  - comment: Catalogue API
    port: 8001
    endpoints:
      - path: /
  - comment: Cart API
    port: 8002
    endpoints:
      - path: /
```

You can additionally specify `hostname` property to make service _only_ respond to requests that contain specific `Host`
HTTP header:

```yaml
services:
  - comment: I'm like Google
    port: 8001
    hostname: www.google.com
    endpoints:
      - path: /
```

### SSL Support

Enabling SSL for service is as easy as specifying `ssl: true` for it:

```yaml
services:
  - comment: This requires 'https://' to be used by a client
    port: 443
    ssl: true
```

If you want to use SSL-enabled mock inside browser (or other client), you would need to
add [Mockintosh's self-signed certificate](https://github.com/up9inc/mockintosh/tree/main/mockintosh/ssl) into trusted
store.

In case you want Mockintosh to use your SSL certificate and key, just provide it as below:

```yaml
services:
  - comment: This requires 'https://' to be used by a client
    port: 443
    ssl: true
    sslCertFile: path/to/cert.crt
    sslKeyFile: path/to/cert.key
```

### Multiple Services on Same Port (Virtual Hosts)

You can also serve multiple services from the same port number, if you provide them with different hostnames. This is
handy when you serve multiple microservice mocks from single container:

```yaml
services:
  - comment: "First service"
    hostname: "service1.example.com"
    port: 80
  - comment: "Second service"
    hostname: "service2.example.com"
    port: 80
```

_Note: You may want to play with your client's `/etc/hosts` file contents when using virtual hosts._

## Defining Endpoints

The fields of an endpoint are shown below:

```yaml
endpoints: # List of the endpoints in your microservice
  - path: "/users" # Path of the endpoint
    method: GET # The HTTP verb
    response: .. # Response
```

### Varying Responses / Scenario Support

The `response` field under `endpoint` can be an array too. If this field is an array then this is looped for each
request. For example, considering the configuration below:

```yaml
response:
  - "@index.html"
  - headers:
      content-type: image/png
    body: "@subdir/image.png"
  - just some text
```

1. request: `index.html` file is returned with `Content-Type: text/html` header.
2. request: `subdir/image.png` image is returned with `Content-Type: image/png` header.
3. request: `just some text` is returned with `Content-Type: text/html` header.
4. request: `index.html` again and so on...

The looping can be disabled with setting `multiResponsesLooped` to `false`:

```yaml
multiResponsesLooped: false
response:
  - "@index.html"
  - headers:
      content-type: image/png
    body: "@subdir/image.png"
  - just some text
```

In this case, on 4th request, the endpoint returns `410` status code with an empty response body.

### Datasets

One can specify a `dataset` field under `endpoint` to directly inject variables into response templating.

This field can be string that starts with `@` to indicate a path that points to an external JSON file
like `@subdir/dataset.json` or an array:

```yaml
dataset:
  - var1: val1
  - var1: val2
response: 'dataset: {{var1}}'
```

This `dataset` is looped just like how [Multiple responses](#multiple-responses) are looped:

1. request: `dataset: val1` is returned.
2. request: `dataset: val2` is returned.
3. request: `dataset: val1` is returned.

The looping can be disabled with setting `datasetLooped` to `false`:

```yaml
datasetLooped: false
dataset:
  - var1: val1
  - var1: val2
response: 'dataset: {{var1}}'
```

In this case, on 3rd request, the endpoint returns `410` status code with an empty response body.

## Global Settings

## Automatic CORS (Cross-Origin Resource Sharing)

`OPTIONS` method has a special behavior in the mock server. Unless there is an endpoint with `method: options`
specified and matched according to the request matching rules, any endpoint (no matter what HTTP method it is) also
accepts `OPTIONS` requests if the `Origin` header is supplied. The mock server will respond such requests with `204`.

For any request that has `Origin` header provided, the mock server will set `Origin` and `Access-Control-Allow-Headers`
headers in the response according to the `Origin` and `Access-Control-Request-Headers` in the request headers. It will
also set `Access-Control-Allow-Methods` header to `DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT`.

## Advanced Templating with Jinja2

You can specifiy the templating engine on top of the file like `templatingEngine: "Jinja2"` or inside the response.

A response example that leverages Jinja2 templating and Faker is shown below:

```j2
{
  "users": [{% for n in range(request.queryString.total) %}
    {
      "id": {{ randomInteger(10000, 100000) }},
      "firstName": "{{ fake.first_name() }}",
      "lastName": "{{ fake.last_name() }}",
      "friends": [{% for n in range(range(5) | random) %}
        {
          "id": "{{ uuid() }}"
        }{% if not loop.last %},{% endif %}
      {% endfor %}]
    }{% if not loop.last %},{% endif %}
  {% endfor %}],
  "total": {{ request.queryString.total }}
}
```
