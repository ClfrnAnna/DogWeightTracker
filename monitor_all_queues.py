# monitor_all_queues.py
import asyncio
import aio_pika
import os
import json
from datetime import datetime


async def monitor_all_queues():
    connection = await aio_pika.connect_robust(f"amqp://{os.getenv('RABBITMQ_USER')}:{os.getenv('RABBITMQ_PASSWORD')}@rabbitmq:5672/")

    async with connection:
        channel = await connection.channel()

        print(f"\n=== Мониторинг RabbitMQ Очередей {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
        for instance_num in [1, 2]:
            queue_name = f"dog_weight_queue_instance_{instance_num}"

            try:
                queue = await channel.get_queue(queue_name)
                if queue:
                    info = await queue.declare(passive=True)

                    print(f"\nОчередь {queue_name}:")
                    print(f"  • Сообщений: {info.message_count}")
                    print(f"  • Потребителей: {info.consumer_count}")
                    print(f"  • Состояние: Активна")

                    if info.message_count > 0:
                        print(f"  • Примеры сообщений:")
                        messages_to_show = min(3, info.message_count)

                        for i in range(messages_to_show):
                            message = await queue.get(no_ack=False)
                            if message:
                                body = json.loads(message.body.decode('utf-8'))
                                print(f"    [{i + 1}] Тип: {body.get('type', 'unknown')}, "
                                      f"Данные: {json.dumps(body.get('data', {}), ensure_ascii=False)[:100]}...")
                                await message.ack()
                else:
                    print(f"\nОчередь {queue_name}: Не найдена")

            except Exception as e:
                print(f"\nОчередь {queue_name}: Ошибка - {str(e)}")

        print("\n=== Конец отчета ===")


if __name__ == "__main__":
    asyncio.run(monitor_all_queues())