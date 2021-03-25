FROM java:latest

EXPOSE 9092
WORKDIR /tmp
ADD https://apache-mirror.rbc.ru/pub/apache/kafka/2.7.0/kafka_2.13-2.7.0.tgz .

RUN tar -xvzf kafka_2.13-2.7.0.tgz
WORKDIR /tmp/kafka_2.13-2.7.0
RUN echo advertised.listeners=PLAINTEXT://localhost:9092 >> config/server.properties
ENTRYPOINT sh -c "bin/zookeeper-server-start.sh config/zookeeper.properties &" && bin/kafka-server-start.sh config/server.properties