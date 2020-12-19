import logging

from mockintosh import Request, Response


def intercept_for_logging(req: Request, resp: Response):
    logging.info("Processed intercepted request: %r, produced response: %r", req, resp)


def intercept_for_modifying(req: Request, resp: Response):
    # should have access to request path, query string, headers, body
    if req.path == '/interceptor-modified':
        # should allow reading and modifying response status code, headers, body
        resp.status = 204
        resp.headers.add("someheader", "someval")
        resp.text = "intercepted"

