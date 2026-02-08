import aio_pika
import json
import os
from typing import List, Dict, Any
from datetime import datetime


class RabbitMQConfig:
    def __init__(self):
        self.username = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
        self.password = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")
        self.host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        self.port = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.vhost = os.getenv("RABBITMQ_DEFAULT_VHOST", "/")
        self.queue_name = os.getenv("RABBITMQ_QUEUE_NAME", "dog_weight_queue")
        self.instance_name = os.getenv("INSTANCE_NAME", "unknown")

    @property
    def connection_string(self) -> str:
        return f"amqp://{self.username}:{self.password}@{self.host}:{self.port}/{self.vhost}"


class RabbitMQClient:
    def __init__(self, config: RabbitMQConfig = None):
        self.config = config or RabbitMQConfig()
        self.connection = None
        self.channel = None
        self.queue = None

    @property
    def queue_name(self):
        return self.config.queue_name

    @property
    def instance_name(self):
        return self.config.instance_name

    async def connect(self):
        self.connection = await aio_pika.connect_robust(self.config.connection_string)
        self.channel = await self.connection.channel()
        self.queue = await self.channel.declare_queue(self.config.queue_name,
                                                      durable=True)
        print(f"Connected to RabbitMQ: queue={self.config.queue_name}, instance={self.config.instance_name}")

    async def publish_message(self, message: Dict[str, Any], operation: str = None):
        if not self.connection:
            await self.connect()
        full_message = {**message,
                        "operation": operation or "unknown",
                        "instance": self.config.instance_name,
                        "queue": self.config.queue_name,
                        "timestamp": datetime.now().isoformat()}

        message_body = json.dumps(full_message).encode()
        await self.channel.default_exchange.publish(aio_pika.Message(body=message_body,
                                                                     delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                                                                     timestamp=datetime.now(),
                                                                     headers={"instance": self.config.instance_name,
                                                                              "queue": self.config.queue_name}),
                                                    routing_key=self.config.queue_name)

        return full_message

    async def consume_all_messages(self) -> List[Dict[str, Any]]:
        if not self.connection:
            await self.connect()
        messages = []
        async with await self.channel.declare_queue(self.config.queue_name, durable=True) as queue:
            while True:
                message = await queue.get(fail=False)
                if message:
                    await message.ack()
                    message_body = json.loads(message.body.decode())
                    enriched_message = {"body": message_body,
                                        "headers": dict(message.headers) if message.headers else {},
                                        "timestamp": message.timestamp.isoformat() if message.timestamp else None,
                                        "message_id": message.message_id,
                                        "redelivered": message.redelivered,
                                        "queue": self.config.queue_name}
                    messages.append(enriched_message)
                else:
                    break

        return messages

    async def get_queue_stats(self) -> Dict[str, Any]:
        if not self.connection:
            await self.connect()

        queue = await self.channel.declare_queue(self.config.queue_name, passive=True)
        return {"queue_name": queue.name,
                "message_count": queue.declaration_result.message_count,
                "consumer_count": queue.declaration_result.consumer_count,
                "instance": self.config.instance_name,
                "timestamp": datetime.now().isoformat()}

    async def purge_queue(self) -> Dict[str, Any]:
        if not self.connection:
            await self.connect()

        queue = await self.channel.declare_queue(self.config.queue_name, passive=True)
        message_count = queue.declaration_result.message_count

        await queue.purge()

        return {"queue_name": queue.name,
                "purged_messages": message_count,
                "instance": self.config.instance_name,
                "timestamp": datetime.now().isoformat()}

    async def close(self):
        if self.connection:
            await self.connection.close()
            print(f"Closed RabbitMQ connection for instance: {self.config.instance_name}")


rabbitmq_clients = {}


async def get_rabbitmq_client() -> RabbitMQClient:
    instance_name = os.getenv("INSTANCE_NAME", "unknown")

    if instance_name not in rabbitmq_clients:
        config = RabbitMQConfig()
        rabbitmq_clients[instance_name] = RabbitMQClient(config)
        await rabbitmq_clients[instance_name].connect()

    return rabbitmq_clients[instance_name]