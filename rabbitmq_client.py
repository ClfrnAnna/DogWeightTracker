import os
import json
import asyncio
from typing import Optional, Callable, List
import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType
import logging

logger = logging.getLogger(__name__)


class RabbitMQClient:
    def __init__(self, instance_number: int = 1):
        self.instance_number = instance_number
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.queue: Optional[aio_pika.Queue] = None
        self.exchange: Optional[aio_pika.Exchange] = None

        self.host = os.getenv('RABBITMQ_HOST', 'rabbitmq')
        self.port = int(os.getenv('RABBITMQ_PORT', 5672))
        self.username = os.getenv('RABBITMQ_USER', 'admin')
        self.password = os.getenv('RABBITMQ_PASSWORD', 'admin123')
        self.vhost = os.getenv('RABBITMQ_DEFAULT_VHOST', '/')

        self.queue_name = f"dog_weight_queue_instance_{self.instance_number}"
        self.exchange_name = f"dog_weight_exchange_instance_{self.instance_number}"

    async def connect(self):
        try:
            connection_string = f"amqp://{self.username}:{self.password}@{self.host}:{self.port}{self.vhost}"
            self.connection = await aio_pika.connect_robust(connection_string, timeout=10)
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=1)
            self.exchange = await self.channel.declare_exchange(self.exchange_name,
                                                                ExchangeType.DIRECT,
                                                                durable=True)

            self.queue = await self.channel.declare_queue(self.queue_name,
                                                          durable=True,
                                                          arguments={'x-message-ttl': 86400000,
                                                                     'x-max-length': 10000, })

            await self.queue.bind(self.exchange, routing_key=self.queue_name)
            logger.info(f"RabbitMQ подключен. Очередь: {self.queue_name}")
            return True

        except Exception as e:
            logger.error(f"Ошибка подключения к RabbitMQ: {e}")
            return False

    async def publish_message(self, message_type: str, data: dict, routing_key: Optional[str] = None):
        if not self.channel:
            await self.connect()

        try:
            message_body = {'type': message_type,
                            'instance': self.instance_number,
                            'timestamp': asyncio.get_event_loop().time(),
                            'data': data}

            message = Message(body=json.dumps(message_body).encode('utf-8'),
                              delivery_mode=DeliveryMode.PERSISTENT,
                              content_type='application/json',
                              headers={'instance': self.instance_number,
                                       'message_type': message_type})

            routing_key = routing_key or self.queue_name
            await self.exchange.publish(message, routing_key=routing_key)
            logger.debug(f"Сообщение опубликовано в очередь {self.queue_name}, тип: {message_type}")

        except Exception as e:
            logger.error(f"Ошибка публикации сообщения: {e}")

    async def consume_messages(self, callback: Callable):
        if not self.queue:
            await self.connect()

        try:
            async with self.queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            body = json.loads(message.body.decode('utf-8'))
                            await callback(body)
                        except Exception as e:
                            logger.error(f"Ошибка обработки сообщения: {e}")

        except Exception as e:
            logger.error(f"Ошибка в потребителе: {e}")

    async def get_queue_info(self) -> dict:
        if not self.queue:
            await self.connect()

        try:
            queue_info = await self.queue.declare(passive=True)

            return {'instance_number': self.instance_number,
                    'queue_name': self.queue_name,
                    'message_count': queue_info.message_count,
                    'consumer_count': queue_info.consumer_count,
                    'state': 'active' if self.connection else 'inactive'}
        except Exception as e:
            logger.error(f"Ошибка получения информации об очереди: {e}")
            return {'instance_number': self.instance_number,
                    'queue_name': self.queue_name,
                    'error': str(e),
                    'state': 'error'}

    async def close(self):
        try:
            if self.connection:
                await self.connection.close()
                logger.info("Подключение к RabbitMQ закрыто")
        except Exception as e:
            logger.error(f"Ошибка при закрытии подключения: {e}")

    async def get_all_messages(self, max_messages: int = 1000, auto_ack: bool = True) -> List[dict]:
        if not self.queue:
            await self.connect()

        messages = []
        message_count = 0

        try:
            queue_info = await self.queue.declare(passive=True)
            available_messages = min(queue_info.message_count, max_messages)

            logger.info(f"В очереди {self.queue_name} найдено {queue_info.message_count} сообщений, "
                        f"читаем {available_messages} из них")

            for i in range(available_messages):
                try:
                    message = await asyncio.wait_for(self.queue.get(no_ack=auto_ack), timeout=1.0)

                    if message:
                        body = json.loads(message.body.decode('utf-8'))
                        messages.append(body)
                        if not auto_ack:
                            await message.ack()

                        message_count += 1

                except asyncio.TimeoutError:
                    break
                except Exception as e:
                    logger.error(f"Ошибка при чтении сообщения {i}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Ошибка при чтении всех сообщений: {e}")

        logger.info(f"Прочитано {len(messages)} сообщений из очереди {self.queue_name}")
        return messages

    async def get_message_count(self) -> int:
        if not self.queue:
            await self.connect()

        try:
            queue_info = await self.queue.declare(passive=True)
            return queue_info.message_count
        except Exception as e:
            logger.error(f"Ошибка получения количества сообщений: {e}")
            return 0

    async def peek_messages(self, limit: int = 50) -> List[dict]:
        if not self.queue:
            await self.connect()

        messages = []

        try:
            queue_info = await self.queue.declare(passive=True)
            available_messages = min(queue_info.message_count, limit)
            temp_channel = await self.connection.channel()
            temp_queue = await temp_channel.declare_queue(self.queue_name,
                                                          durable=True,
                                                          arguments={'x-message-ttl': 86400000,
                                                                     'x-max-length': 10000, })

            for i in range(available_messages):
                try:
                    message = await asyncio.wait_for(temp_queue.get(no_ack=True), timeout=0.5)

                    if message:
                        body = json.loads(message.body.decode('utf-8'))
                        messages.append(body)
                    else:
                        break

                except asyncio.TimeoutError:
                    break
                except Exception as e:
                    logger.error(f"Ошибка при просмотре сообщения {i}: {e}")

            await temp_channel.close()

        except Exception as e:
            logger.error(f"Ошибка при просмотре сообщений: {e}")

        return messages

    async def purge_queue(self) -> int:
        if not self.queue:
            await self.connect()

        try:
            queue_info = await self.queue.declare(passive=True)
            message_count = queue_info.message_count

            await self.queue.purge()
            logger.info(f"Очередь {self.queue_name} очищена, удалено {message_count} сообщений")

            return message_count
        except Exception as e:
            logger.error(f"Ошибка при очистке очереди: {e}")
            return 0


rabbitmq_client: Optional[RabbitMQClient] = None


async def get_rabbitmq_client():
    global rabbitmq_client
    if not rabbitmq_client:
        instance_number = int(os.getenv('INSTANCE_NUMBER', 1))
        rabbitmq_client = RabbitMQClient(instance_number)
        await rabbitmq_client.connect()
    return rabbitmq_client
