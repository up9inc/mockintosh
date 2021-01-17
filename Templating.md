# Response Templating

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

By default, dynamic templates use [Handlebars](https://handlebarsjs.com/guide/) syntax that looks like
this: `{{namedValue}}` or `{{request.path}}` or `{{fake.address}}` etc.

_Note: To switch into [Jinja2](https://jinja.palletsprojects.com/en/2.11.x/) as templating engine, use
the `templatingEngine` option of [configuration syntax](Configuring.md#advanced-templating-with-jinja2)._

Below is the reference of available dynamic value generators.

### Random

- `random.int 10 20` - random integer between 10 and 20 (inclusive)
- `random.float '-0.5' '20.7' 3` - random float (between `-0.5` and `20.7` , inclusive) with 3 digit precision, you have to keep range values in quotes
- `random.ascii 5` - sequence of ASCII characters, length 5
- `random.alphanum 5` - sequence of alphanumeric characters, length 5
- `random.hex 16` - sequence of hexadecimal characters, length 16
- `random.uuid4` - UUID4 generator

For random names, addresses etc, please refer to [Faker's](#faker) functionality.

### Date

- `date.timestamp` - UNIX timestamp (UTC)
- `date.timestamp -42` - UNIX timestamp (UTC) shifted 42 back
- `date.ftimestamp` - UNIX timestamp (UTC) in floating-point format (default: 3 decimal percision)
- `date.ftimestamp 0.0 7` - UNIX timestamp (UTC) in floating-point format with 7 decimal precision
- `date.ftimestamp 3.14` - UNIX timestamp (UTC) in floating-point format with 3 decimal precision, shifted 3.14 forward
- `date.date` - Current date (UTC) (default format: `%Y-%m-%dT%H:%M:%S.%f`)
- `date.date '%Y-%m-%d %H:%M'` Current date (UTC) with format `%Y-%m-%d %H:%M`. For date and time formates please refer to [`strftime`](https://strftime.org/) reference.

Here is a list of date shifting examples as a Handlebars response template:

```hbs
{
  "now": "{{ date.date '%Y-%m-%d %H:%M %f' }}",
  "1_week_back": "{{ date.date '%Y-%m-%d %H:%M %f' -604800 }}",
  "1_week_forward": "{{ date.date '%Y-%m-%d %H:%M %f' 604800 }}",
  "1_day_back": "{{ date.date '%Y-%m-%d %H:%M %f' -86400 }}",
  "1_day_forward": "{{ date.date '%Y-%m-%d %H:%M %f' 86400 }}",
  "1_hour_back": "{{ date.date '%Y-%m-%d %H:%M %f' -3600 }}",
  "1_hour_forward": "{{ date.date '%Y-%m-%d %H:%M %f' 3600 }}",
  "1_minute_back": "{{ date.date '%Y-%m-%d %H:%M %f' -60 }}",
  "1_minute_forward": "{{ date.date '%Y-%m-%d %H:%M %f' 60 }}"
}
```

### Faker

[Faker](https://faker.readthedocs.io/en/master/providers.html) library is provided for generating some dynamic data.
It is available as `fake` object. Refer to the [official docs](https://faker.readthedocs.io/en/master/providers.html) for all capabilities. Below are some examples:

```hbs
{
  "hexify_args": "{{ fake.hexify text="MAC Address: ^^:^^:^^:^^:^^:^^" upper=true }}",
  "lexify_args": "{{ fake.lexify text="Random Identifier: ??????????" }}",
  "numerify_args": "{{ fake.numerify text="Intel Core i%-%%##K vs AMD Ryzen % %%##X" }}",
  "random_choices": "{{ fake.random_choices elements=( array 'a' 'b' 'c' 'd' 'e' ) }}",
  "random_digit": {{ fake.random_digit }},
  "random_element": "{{ fake.random_element elements=( array 'a' 'b' 'c' 'd' 'e' ) }}",
  "random_elements": {{ tojson ( fake.random_elements elements=( array 'a' 'b' 'c' 'd' 'e' ) length=3 unique=True ) }},
  "random_int_args": {{ fake.random_int min=10000 max=50000 step=500 }},
  "random_letter": "{{ fake.random_letter }}",
  "random_letters": {{ tojson ( fake.random_letters ) }},
  "random_letters_args": {{ tojson ( fake.random_letters length=32 ) }},
  "random_lowercase_letter": "{{ fake.random_lowercase_letter }}",
  "random_sample": {{ tojson ( fake.random_sample elements=( array 'a' 'b' 'c' 'd' 'e' ) ) }},
  "random_uppercase_letter": "{{ fake.random_uppercase_letter }}",
  "first_name": "{{ fake.first_name }}",
  "first_name_female": "{{ fake.first_name_female }}",
  "first_name_male": "{{ fake.first_name_male }}",
  "first_name_nonbinary": "{{ fake.first_name_nonbinary }}",
  "last_name": "{{ fake.last_name }}",
  "last_name_female": "{{ fake.last_name_female }}",
  "last_name_male": "{{ fake.last_name_male }}",
  "last_name_nonbinary": "{{ fake.last_name_nonbinary }}",
  "address": "{{ fake.address }}",
  "city": "{{ fake.city }}",
  "country": "{{ fake.country }}"
}
```

Rendered:

```json
{
  "hexify_args": "MAC Address: 84:DE:AD:1C:AD:D7",
  "lexify_args": "Random Identifier: ZDGINMgIkX",
  "numerify_args": "Intel Core i7-8517K vs AMD Ryzen 3 8887X",
  "random_choices": "['b', 'a', 'd', 'a', 'b']",
  "random_digit": 9,
  "random_element": "d",
  "random_elements": ["a", "a", "d"],
  "random_int_args": 26500,
  "random_letter": "A",
  "random_letters": ["M", "S", "N", "T", "r", "m", "p", "j", "R", "n", "g", "g", "A", "w", "o", "d"],
  "random_letters_args": ["F", "L", "X", "R", "Z", "T", "f", "k", "C", "v", "U", "d", "d", "S", "p", "j", "s", "F", "M", "X", "k", "J", "P", "R", "W", "m", "i", "A", "x", "o", "r", "H"],
  "random_lowercase_letter": "i",
  "random_sample": ["c", "a", "b"],
  "random_uppercase_letter": "U",
  "first_name": "Mark",
  "first_name_female": "Sharon",
  "first_name_male": "Brian",
  "first_name_nonbinary": "Jessica",
  "last_name": "Campbell",
  "last_name_female": "Rodriguez",
  "last_name_male": "Combs",
  "last_name_nonbinary": "Mcmillan",
  "address": "035 Angela Brook\nElizabethhaven, MO 35984",
  "city": "Hannaport",
  "country": "Burkina Faso"
}
```

### Counters

There is special kind of template helper, offering named counters like `{{counter 'counterName'}}`. The counters are global and identified by name. You can also refer to last value of counter by its name like this: `{{counterName}}`

### Request Object

You can reference parts of HTTP request in response templates. It is available as `request` object. These are the most
useful attributes:

- `request.path` - The path part of the URI e.g. `/some/path`.
- `request.path.<n>` - The specific component part of the URI
- `request.headers.<key>` - A request header e.g. `request.headers.accept`.
- `request.queryString.<key>` - A query parameter e.g. `request.queryString.a` is `hello world`.
- `request.body` - The raw request body as a whole. Can be `str`, `bytes` or `dict`.
- `request.formData.<key>` - The `POST` parameters sent in a `application/x-www-form-urlencoded` request
  e.g. `request.formData.param1` is `value1`.
- `request.files.<key>` - The fields in a `multipart/form-data` request.


And some less frequently used:

- `request.method` - [HTTP method](https://www.w3.org/Protocols/rfc2616/rfc2616-sec9.html)
- `request.uri` - URI, full path segments including the query string e.g. `/some/path?a=hello%20world&b=3`.
- `request.host` - Full address of host e.g. `localhost:8001`.
- `request.hostName` - Only the hostname e.g. `localhost`.
- `request.protocol` - The HTTP protocol e.g. `http` or `https`.
- `request.remoteIp` - The IP address of the client e.g. `127.0.0.1`.
- `request.version` - HTTP version e.g. `HTTP/1.1`, [see](https://tools.ietf.org/html/rfc2145).

### Using JSONPath Syntax

You can reference certain fields from request's JSON by using `jsonPath` helper like this: `jsonPath request.json '$.key'`.

### Other Template Helpers

#### `escapeHtml(text)`

`{{ escapeHtml '& < \" >' }}` a helper to escape HTML special characters. (see [`html.escape`](https://wiki.python.org/moin/EscapingHtml))

#### `tojson(text)` (Handlebars)

The equivalent of [`tojson`](https://jinja.palletsprojects.com/en/2.10.x/templates/#tojson) filter in Jinja2.

Jinja2 usage: `{{ fake.random_letters() | tojson }}`

Handlebars usage: `{{ tojson ( fake.random_letters ) }}`

#### `array(*args)` (Handlebars)

Provides array support in parameters. `{{ array 'a' 'b' 'c' 'd' 'e' }}` returns `['a', 'b', 'c', 'd', 'e']`.
