# Chupeta

We respect the achievements of predecessors (Wiremock, Mockoon etc), we offer similar syntax.

We aim for cloud-native/microservices, so the main case is many mocks running at once. Also, we aim for the smallest Docker
image size, the smallest RAM requirement.

Ability to serve multiple services from one container, without much resource overhead - mockoon does it

Ability to provide custom code that alters responses - hoverfly’s middleware

Ability to provide datasets for lists of possible values

Ability to refer to external file containing body

Ability to reference request parts in response - handlebars templating in wiremock and mockoon

Variants of responses based on rules

Have JSON schema for configuration language - avoid Mockoon’s mistake of not documenting enough

Ability to control a lot of response via request headers - for quick experimentation and code-level configuration in any language

Import from OpenAPI and Postman collections

Ability to attach handler to request/response logger, for integration

Ability to catch unhandled requests and turn those into configuration templates

API to modify configuration remotely, maybe programmatically (for UP9 live control)

JSON+YAML config format

Ability to get stats on mock items covered

JSON schema validation of request bodies

Performance testing mode, round-robining the delays/500/400/RST, offering “profile” of fuzziness

```json5
{
  "services": [
    
  ]
}
```