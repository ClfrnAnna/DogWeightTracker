import os
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, String, Float, DateTime, Date, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL",
                         "postgresql+asyncpg://postgres:password@localhost:5432/dog_weight_tracker")

engine = create_async_engine(DATABASE_URL, echo=True)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


class DogDB(Base):
    __tablename__ = "dogs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True, index=True)
    breed = Column(String(100), nullable=False)
    ideal_weight = Column(Float, nullable=False)
    current_weight = Column(Float, nullable=False)
    birth_date = Column(Date, nullable=True)
    activity_level = Column(Float, nullable=False, default=1.6)
    created_date = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": str(self.id),
                "name": self.name,
                "breed": self.breed,
                "ideal_weight": self.ideal_weight,
                "current_weight": self.current_weight,
                "birth_date": self.birth_date.isoformat() if self.birth_date else None,
                "activity_level": self.activity_level,
                "created_date": self.created_date.isoformat()}


class WeightRecordDB(Base):
    __tablename__ = "weight_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dog_id = Column(UUID(as_uuid=True), ForeignKey("dogs.id", ondelete="CASCADE"), nullable=False, index=True)
    dog_name = Column(String(100), nullable=False)
    weight = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)
    date = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {"id": str(self.id),
                "dog_id": str(self.dog_id),
                "dog_name": self.dog_name,
                "weight": self.weight,
                "notes": self.notes,
                "date": self.date.isoformat()}


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
