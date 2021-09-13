FROM up9inc/mockintosh

RUN apt update && apt install -y rsync docker.io build-essential

RUN pip uninstall -y mockintosh

RUN echo 127.0.0.1 service1.example.com >> /etc/hosts
RUN echo 127.0.0.1 service2.example.com >> /etc/hosts
RUN echo 127.0.0.1 service3.example.com >> /etc/hosts

