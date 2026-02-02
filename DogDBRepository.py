from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from Dog import Dog, ActivityLevel
from database import DogDB, WeightRecordDB


class DogDBRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_dog(self, dog: Dog) -> DogDB:
        dog_db = DogDB(name=dog.name,
                       breed=dog.breed,
                       ideal_weight=dog.ideal_weight,
                       current_weight=dog.current_weight,
                       birth_date=dog.birth_date,
                       activity_level=dog.activity_level.value)

        self.session.add(dog_db)
        await self.session.flush()

        return dog_db

    async def get_dog(self, dog_id: str) -> Optional[DogDB]:
        try:
            uuid_id = UUID(dog_id)
        except ValueError:
            return None

        result = await self.session.execute(select(DogDB).where(DogDB.id == uuid_id))
        return result.scalar_one_or_none()

    async def get_dog_by_name(self, name: str) -> Optional[DogDB]:
        result = await self.session.execute(select(DogDB).where(DogDB.name == name))
        return result.scalar_one_or_none()

    async def get_all_dogs(self) -> List[DogDB]:
        result = await self.session.execute(select(DogDB).order_by(DogDB.name))
        return list(result.scalars().all())

    async def update_dog(self, dog_id: str, **kwargs) -> Optional[DogDB]:
        dog = await self.get_dog(dog_id)
        if not dog:
            return None

        for key, value in kwargs.items():
            if hasattr(dog, key) and value is not None:
                setattr(dog, key, value)

        await self.session.flush()
        return dog

    async def delete_dog(self, dog_id: str) -> bool:
        dog = await self.get_dog(dog_id)
        if not dog:
            return False

        await self.session.delete(dog)
        return True

    async def add_weight_record(self, dog_id: str, weight: float, notes: str = "") -> Optional[WeightRecordDB]:
        dog = await self.get_dog(dog_id)
        if not dog:
            return None

        dog.current_weight = weight

        record = WeightRecordDB(dog_id=dog.id,
                                dog_name=dog.name,
                                weight=weight,
                                notes=notes)

        self.session.add(record)
        await self.session.flush()

        return record

    async def get_dog_records(self, dog_id: str) -> List[WeightRecordDB]:
        try:
            uuid_id = UUID(dog_id)
        except ValueError:
            return []

        result = await self.session.execute(select(WeightRecordDB)
                                            .where(WeightRecordDB.dog_id == uuid_id)
                                            .order_by(WeightRecordDB.date))
        return list(result.scalars().all())

    async def get_recent_records(self, limit: int = 10) -> List[WeightRecordDB]:
        result = await self.session.execute(select(WeightRecordDB)
                                            .order_by(desc(WeightRecordDB.date))
                                            .limit(limit))
        return list(result.scalars().all())

    async def get_total_records_count(self) -> int:
        result = await self.session.execute(select(func.count(WeightRecordDB.id)))
        return result.scalar()

    async def get_dogs_count(self) -> int:
        result = await self.session.execute(select(func.count(DogDB.id)))
        return result.scalar()

    @staticmethod
    def convert_to_dog_object(dog_db: DogDB) -> Dog:
        activity_level_value = dog_db.activity_level
        activity_level = ActivityLevel.MEDIUM

        for level in ActivityLevel:
            if level.value == activity_level_value:
                activity_level = level
                break

        dog = Dog(name=dog_db.name,
                  breed=dog_db.breed,
                  ideal_weight=dog_db.ideal_weight,
                  current_weight=dog_db.current_weight,
                  birth_date=dog_db.birth_date,
                  activity_level=activity_level)

        dog.id = str(dog_db.id)
        dog.created_date = dog_db.created_date

        return dog
