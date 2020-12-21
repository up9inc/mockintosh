import logging

from mockintosh import Request, Response


def intercept_for_logging(req: Request, resp: Response):
    logging.info("Processed intercepted request: %r, produced response: %r", req, resp)


def intercept_for_modifying(req: Request, resp: Response):
    # should have access to request path, query string, headers, body
    if req.path == '/interceptor-modified':
        # should allow reading and modifying response status code, headers, body
        resp.force_update = True
        resp.status_code = 201
        resp.headers['someheader'] = 'some-i-val'
        resp.body = 'intercepted'
