cert:
	openssl req \
		-new \
		-newkey rsa:4096 \
		-days 3650 \
		-nodes \
		-x509 \
		-subj "/C=US/ST=Denial/L=Springfield/O=Dis/CN=www.example.com" \
		-keyout mockintosh/res/ssl/key.pem \
		-out mockintosh/res/ssl/cert.pem
