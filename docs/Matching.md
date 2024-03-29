# Request Matching Logic

The general rule for matching request to endpoint definition is "take first endpoint that fully matches criteria". This
means that there can be multiple endpoints with same `path` and `method`, but different `queryString`/`headers`/`body`
criteria. If no match is found a `404` response will be returned.

_Note: there is a special priority given to constant `path` prefixes over parameterized ones,
see [explanation](#static-value-priority) below._

## Path

URL `path` is the main criteria of matching endpoint to request, and the only required option in endpoint definition.

You can use `{% raw %}{{varname}}{% endraw %}` syntax to specify a path parameter in any segment of your paths and it will become available
for using in the response template:

```yaml
{% raw %}endpoints:
  - path: "/parameterized/{{myVar}}/someval"
    response: 'Here is: {{myVar}}'{% endraw %}
```

With Mockintosh it's possible to use regular expressions in path segments:

```yaml
{% raw %}- path: "/match/{{regEx 'prefix-.*'}}/someval"
  response: 'regex match: {{request.path}}'{% endraw %}
```

so that a request like `curl http://localhost:8001/match/prefix-hello_world/someval` would
return `regex match: /match/prefix-hello_world/someval`

It's also possible to use regular expression capture groups in path segments, as templating items:

```yaml
{% raw %}- path: "/match/{{regEx 'prefix-(.*)' 'myVar'}}/someval"
  response: 'regex capture group: {{myVar}}'{% endraw %}
```

so that a request like `curl http://localhost:8001/match/prefix-hello_world/someval` would
return `regex capture group: hello_world`

You can use as many path parameters and regex capture groups you want:

```yaml
{% raw %}- path: "/parameterized5/text/{{var1}}/{{regEx 'prefix-(.*)-(.*)-suffix' 'var2' 'var3'}}/{{var4}}/{{regEx 'prefix2-(.*)' 'var5'}}"
  response: 'var1: {{var1}}, var2: {{var2}}, var3: {{var3}}, var4: {{var4}}, var5: {{var5}}'{% endraw %}
```

### Automatic `regEx` Conversion

When you define a variable for a portion of a path segment like the example below, it's automatically detected and
converted to a regex function behind the scenes.

E.g.:

```yaml
{% raw %}- path: "/hello-{{somevar}}/another"
  response: 'result: {{somevar}}'{% endraw %}
```

is automatically converted to:

```yaml
{% raw %}- path: "/{{regEx 'hello\-(.*)' 'somevar'}}/another"
  response: 'result: {{somevar}}'{% endraw %}
```

_Note: "Automatic `regEx` Conversion" is not specific to `path` attribute but rather applies to places where templating is possible._

### Automatic Query String Conversion

Similar to the [Automatic RegEx Conversion](#automatic-regex-conversion) mechanic, it's possible to
[match query strings](#query-string)
using the `path` attribute. `path` can be extended to match the `path[?query][#fragment]` portion
of [URI](https://en.wikipedia.org/wiki/Uniform_Resource_Identifier)(`scheme:[//authority]path[?query][#fragment]`)
for practical reasons.

E.g.:

```yaml
{% raw %}- path: "/search?q={{keyword1}}&s={{keyword2}}"
  response: 'result: {{keyword1}} {{keyword2}}'{% endraw %}
```

is automatically converted to:

```yaml
{% raw %}- path: "/search"
  queryString:
    q: "{{keyword1}}"
    s: "{{keyword1}}"
  response: 'result: {{keyword1}} {{keyword2}}'{% endraw %}
```

_Note: "Automatic Query String Conversion" is specific to `path` attribute._

### Static Value Priority

Even if you specified a path parameter for a certain path segment, static values have a higher priority over named
parameters and `regEx`:

```yaml
{% raw %}endpoints:
  - path: "/parameterized/{{myVar}}/someval"
    response: 'Here is: {{myVar}}'
  - path: "/parameterized/staticval/someval"
    response: static path segments have a high priority{% endraw %}
```

so that a request like `curl http://localhost:8001/parameterized/staticval/someval` would
return `static path segments have a high priority`.

## Method

The `method` keyword is used for simple matching to request's verb:

```yaml
endpoints:
  - path: /
    method: PATCH
    response: Patched!
  - path: /
    method: POST
    response: Posted!
```

## Headers

Any header specified in the endpoint description is required to exist in the request headers. The syntax of static
values, parameters, regex match and regex capture groups, is exactly the same with how it works in [path](#path)
matching.

Below is an example configuration which demonstrates the how endpoint alternatives recognized in terms of headers:

```yaml
{% raw %}services:
  - port: 8001
    endpoints:
      - path: "/alternative"
        method: GET
        headers:
          hdr1: myValue
          hdr2: "{{myVar}}"
          hdr3: "{{regEx 'prefix-(.+)-suffix' 'myCapturedVar'}}"
        response:
          body: 'headers match: {{request.headers.hdr1}} {{myVar}} {{myCapturedVar}}'
          status: 201
          headers:
            Set-Cookie:
              - name1={{request.headers.hdr2}}
              - name2={{request.headers.hdr3}}
      - path: "/alternative"
        headers:
          hdr4: another header
        response:
          body: 'hdr4 request header: {{request.headers.hdr4}}'
          headers:
            hdr4: 'hdr4 request header: {{request.headers.hdr4}}'{% endraw %}
```

For the above configuration example here are some example requests and their responses:

- Request: `curl http://localhost:8001/alternative -H "hdr1: wrongValue"` Response: `404`
- Request: `curl http://localhost:8001/alternative -H "hdr1: myValue" -H "hdr2: someValue"` Response: `404`
- Request: `curl http://localhost:8001/alternative -H "hdr1: myValue" -H "hdr2: someValue" -H "hdr3: prefix-invalidCapture"` Response: `404`
- Request: `curl http://localhost:8001/alternative -H "hdr1: myValue" -H "hdr2: someValue" -H "hdr3: prefix-validCapture-suffix"` Response: `201` with `headers match: mvValue someValue validCapture` (also it sets the cookies `name1` to `someValue`
and `name2` to `validCapture`)
- Request: `curl http://localhost:8001/alternative -H "hdr4: another header"` Response: `200` with `hdr4 request header: another header`
- Request: `curl http://localhost:8001/alternative -H "hdr5: another header"` Response: `404`

## Query String

The matching logic for query strings is quite similar to [headers](#headers). Here is the similar example but in terms
of the query strings:

```yaml
{% raw %}services:
  - name: Service1
    port: 8001
    endpoints:
      - path: "/alternative"
        method: GET
        queryString:
          param1: my Value
          param2: "{{myVar}}"
          param3: "{{regEx 'prefix-(.+)-suffix' 'myCapturedVar'}}"
        response:
          body: 'query string match: {{request.queryString.param1}} {{myVar}} {{myCapturedVar}}'
          status: 201
      - path: "/alternative"
          queryString:
            param4: another query string
          response:
            body: 'param4 request query string: {{request.queryString.param4}}'{% endraw %}
```

and these are the example requests and corresponding responses for such a mock server configuration:

- Request: `curl http://localhost:8001/alternative?param1=wrongValue"` Response: `404`
- Request: `curl http://localhost:8001/alternative?param1=my%20Value&param2=someValue"` Response: `404`
- Request: `curl http://localhost:8001/alternative?param1=my%20Value&param2=someValue&param3=prefix-invalidCapture"`
Response: `404`
- Request: `curl http://localhost:8001/alternative?param1=my%20Value&param2=someValue&param3=prefix-validCapture-suffix"`
Response: `201`  with `query string match: mvValue someValue validCapture`
- Request: `curl http://localhost:8001/alternative?param4=another%20query%20string"` Response: `200`
    with `param4 request query string: another query string`
- Request: `curl http://localhost:8001/alternative?param5=another%20query%20string"` Response: `404`

## Body

There are several ways of matching request body: with `regEx` on `text` or with JSON Schema, also you can have criteria
for urlencoded and multipart request bodies.

### Multipart & URL-encoded

To match request by urlencoded or multipart form POST, use `urlencoded` or `multipart` section under `body`. The content of that section is very much like [query string](#query-string) or headers matching by parameter name:

```yaml
{% raw %}services:
  - port: 8001
    endpoints:
      - path: "/body-urlencoded"
        method: POST
        body:
          urlencoded:
            param1: myValue
            param2: "{{myVar}}"
            param3: "{{regEx 'prefix-(.+)-suffix' 'myCapturedVar'}}"
      - path: "/body-multipart"
        method: POST
        body:
          multipart:
            param1: myValue
            param2: "{{myVar}}"
            param3: "{{regEx 'prefix-(.+)-suffix' 'myCapturedVar'}}"{% endraw %}
```

### RegEx

To match request body text using `regEx`, just do it like this:

```yaml
{% raw %}services:
  - name: Mock for Service1
    port: 8001
    endpoints:
      - path: "/endpoint1"
        method: POST
        body:
          text: {{regEx '"jsonkey": "expectedval-(.+)"' 'namedValue'}}{% endraw %}
```

_Note: you can use familiar `regEx` named value capturing for body, as usual._

### JSONSchema

To do the match against [JSON Schema](https://json-schema.org/), please consider this example:

```yaml
services:
  - name: Mock for Service1
    port: 8001
    endpoints:
      - path: "/endpoint1"
        method: POST
        body:
          schema:
            type: object
            properties:
              somekey: { }
            required:
              - somekey
        response: 'endpoint1: body JSON schema matched'
```

and here is a two request example that one matches the JSON schema while the other doesn't match:

- Request:

```bash
curl -X POST http://localhost:8001/endpoint1?param1=wrongValue \
     -H "Accept: application/json"
     -d '{"somekey": "valid"}'
```

Response: `200` - `endpoint1: body JSON schema matched`

- Request:

```bash
curl -X POST http://localhost:8001/endpoint1?param1=wrongValue \
     -H "Accept: application/json"
     -d '{"somekey2": "invalid"}'
```

Response: `400`

If you want to reference JSONSchema from an external file, use it like this:

```yaml
services:
  - name: Mock for Service1
    port: 8001
    endpoints:
      - path: "/endpoint1"
        method: POST
        body:
          schema: "@path/to/schema.json"
```

### GraphQL

The `body` field can also be used to match incoming GraphQL requests.

#### `graphql-query` field

To do that, the `graphql-query` field should be defined under the `body` field:

```yaml
{% raw %}services:
  - name: Mock for Service1
    port: 8001
    endpoints:
      - path: "/endpoint1"
        method: POST
        response:
          headers:
            Content-Type: application/json
          body: '@templates/resp1.json.hbs'
          useTemplating: true
        body:
          graphql-query: |
            query HeroNameAndFriends {
              hero(
                where: {name: {_eq: "{{regEx '(.*)' 'name_eq'}}"}, _and: {age: {_gt: {{regEx '(.*)' 'age_gt'}}}}}
              ) {
                name
                age
                friends {
                  name
                }
              }
            }{% endraw %}
```

The `graphql-query` contains the template for regex generation. So it translates into the regex below:

```graphql
query\ HeroNameAndFriends\ \{\
\ \ hero\(\
\ \ \ \ where:\ \{name:\ \{_eq:\ "(.*)"\},\ _and:\ \{age:\ \{_gt:\ (.*)\}\}\}\
\ \ \)\ \{\
\ \ \ \ name\
\ \ \ \ age\
\ \ \ \ friends\ \{\
\ \ \ \ \ \ name\
\ \ \ \ \}\
\ \ \}\
\}
```

and this regex matches to a GraphQL request like below:

```json
{"query": "query HeroNameAndFriends {\n  hero(\n    where: {name: {_eq: \"hello\"}, _and: {age: {_gt: 30}}}\n  ) {\n    name\n    age\n    friends {\n      name\n    }\n    }\n}\n"}
```

Such that we can respond with a template like this:

```hbs
{% raw %}{
  "data": {
    "hero": {
      "name": "{{ name_eq }}",
      "age": {{ random.int age_gt 50 }},
      "friends": [
        {
          "name": "Luke Skywalker"
        },
        {
          "name": "Han Solo"
        },
        {
          "name": "Leia Organa"
        }
      ]
    }
  }
}{% endraw %}
```

It's possible to define variations of a GraphQL query such that you can select the fields
by adding or subtracting them from the GrahpQL query matching definition:

```yaml
{% raw %}graphql-query: |
  query HeroNameAndFriends {
    hero(
      where: {name: {_eq: "{{regEx '(.*)' 'name_eq'}}"}, _and: {age: {_gt: {{regEx '(.*)' 'age_gt'}}}}}
    ) {
      name
      age
    }
  }{% endraw %}
```

and you would respond to a query like this with response template like below:

```hbs
{% raw %}{
  "data": {
    "hero": {
      "name": "{{ name_eq }}",
      "age": {{ random.int age_gt 50 }}
    }
  }
}{% endraw %}
```

#### `graphql-variables` field

Besides the `graphql-query` field, you can define an additional field named `graphql-variables` to
specify matching criteria for GraphQL variables:

```yaml
{% raw %}services:
  - name: Mock for Service1
    port: 8001
    endpoints:
      - path: "/endpoint1"
        method: POST
        response:
          headers:
            Content-Type: application/json
          body: '@templates/resp1.json.hbs'
          useTemplating: true
        body:
          graphql-query: |
            query HeroNameAndFriends {
              hero(
                where: {name:       {_eq: "{{regEx '(.*)' 'name_eq'}}"}, _and: {age: {_gt: {{regEx '(.*)' 'age_gt'}}}}}
              ) {
                name
                city
              }
            }
          graphql-variables:
            var1: val1
            var2: "{{regEx '\\d'}}"{% endraw %}
```

Such that this would match into a request like below:

```json
{
    "query": "query HeroNameAndFriends {\n  hero(\n    where: {name: {_eq: \"hello\"}, _and: {age: {_gt: 30}}}\n  ) {\n    name\n    city\n     }\n}\n",
    "variables": {
        "var1": "val1",
        "var2": 3
    }
}
```
